#!/usr/bin/env python3
"""SOMBA stats updater — fully automatic, no keys, no prompts.

Scrapes the public follower counts for every enabled platform in
data/stats.json and saves a dated snapshot. It never asks a question:
if a platform can't be read, it quietly reuses that platform's last
known number (flagged so the dashboard can show a small "reused" note).

Runs unattended every week in GitHub Actions, and can also be run by
hand:  python3 update_stats.py

Uses only Python's standard library — nothing to install.
"""

import html as html_lib
import json
import os
import re
import sys
import urllib.request
from datetime import date

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(REPO_DIR, "data", "stats.json")

CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
GOOGLEBOT_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


# ---------------------------------------------------------------- helpers

def http_get(url, user_agent, timeout=25):
    """Fetch a URL and return its body as text. Raises on any failure."""
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            raise RuntimeError("HTTP %s" % resp.status)
        return resp.read().decode("utf-8", errors="replace")


def parse_abbrev(s):
    """Turn '756', '13,800', '13.8K' or '1.2M' into a whole number."""
    s = s.strip().upper().replace(",", "")
    mult = 1
    if s.endswith("K"):
        mult, s = 1_000, s[:-1]
    elif s.endswith("M"):
        mult, s = 1_000_000, s[:-1]
    elif s.endswith("B"):
        mult, s = 1_000_000_000, s[:-1]
    return int(round(float(s) * mult))


# ---------------------------------------------------------------- fetchers
# Each fetcher returns a dict of metrics including "followers",
# or raises an exception (which triggers a silent carry-forward).

def fetch_instagram(p):
    html = http_get(p["url"], GOOGLEBOT_UA)
    m = re.search(
        r'([\d.,]+[KMB]?)\s+Followers,\s+([\d.,]+[KMB]?)\s+Following,\s+([\d.,]+[KMB]?)\s+Posts',
        html,
    )
    if not m:
        raise RuntimeError("follower count not found in the Instagram page")
    return {
        "followers": parse_abbrev(m.group(1)),
        "following": parse_abbrev(m.group(2)),
        "posts": parse_abbrev(m.group(3)),
    }


def fetch_tiktok(p):
    html = http_get(p["url"], CHROME_UA)
    username = p["url"].rstrip("/").rsplit("@", 1)[-1]
    # Anchor to our own account so a "suggested accounts" block can't
    # feed us someone else's numbers. Fall back to first match anywhere.
    idx = html.find('"uniqueId":"%s"' % username)
    region = html[idx : idx + 3000] if idx != -1 else html
    out = {}
    for key, name in (("followerCount", "followers"), ("heartCount", "likes"), ("videoCount", "videos")):
        m = re.search(r'"%s":(\d+)' % key, region) or re.search(r'"%s":(\d+)' % key, html)
        if m:
            out[name] = int(m.group(1))
    if "followers" not in out:
        raise RuntimeError("follower count not found in the TikTok page")
    return out


def fetch_youtube(p):
    # The /about page reliably carries subscriber, video and total-view counts.
    url = p["url"].rstrip("/") + "/about"
    html = http_get(url, CHROME_UA)
    subs = re.search(r'"([\d.,]+[KMB]?)\s+subscribers"', html)
    if not subs:
        raise RuntimeError("subscriber count not found in the YouTube page")
    out = {"followers": parse_abbrev(subs.group(1))}
    vids = re.search(r'"([\d.,]+[KMB]?)\s+videos"', html)
    if vids:
        out["videos"] = parse_abbrev(vids.group(1))
    # viewCountText is the channel total; anchor to it so we don't grab
    # a single video's view count that also appears on the page.
    views = re.search(r'"viewCountText":"([\d.,]+)\s+views"', html)
    if views:
        out["views"] = parse_abbrev(views.group(1))
    return out


def fetch_linkedin(p):
    html = http_get(p["url"], CHROME_UA)
    m = re.search(r'([\d.,]+[KM]?)\s+followers', html, re.IGNORECASE)
    if not m:
        raise RuntimeError("follower count not found in the LinkedIn page")
    return {"followers": parse_abbrev(m.group(1))}


def fetch_facebook(p):
    # No reliable public scrape for Facebook pages; carries forward if enabled.
    raise RuntimeError("Facebook has no automatic fetch")


def fetch_youtube_videos(channel_id):
    """Recent uploads from YouTube's official RSS feed (title, date, views, likes)."""
    url = "https://www.youtube.com/feeds/videos.xml?channel_id=" + channel_id
    xml = http_get(url, CHROME_UA)
    videos = []
    for entry in xml.split("<entry>")[1:]:
        vid = re.search(r"<yt:videoId>([^<]+)</yt:videoId>", entry)
        title = re.search(r"<media:title>([^<]*)</media:title>", entry)
        pub = re.search(r"<published>(\d{4}-\d{2}-\d{2})", entry)
        views = re.search(r'<media:statistics views="(\d+)"', entry)
        likes = re.search(r'<media:starRating[^>]*count="(\d+)"', entry)
        if not (vid and title and pub):
            continue
        videos.append({
            "id": vid.group(1),
            "title": html_lib.unescape(title.group(1)),
            "published": pub.group(1),
            "views": int(views.group(1)) if views else None,
            "likes": int(likes.group(1)) if likes else None,
        })
    if not videos:
        raise RuntimeError("no entries in the YouTube feed")
    return videos


FETCHERS = {
    "instagram": fetch_instagram,
    "tiktok": fetch_tiktok,
    "youtube": fetch_youtube,
    "linkedin": fetch_linkedin,
    "facebook": fetch_facebook,
}


# ---------------------------------------------------------------- carry-forward

def last_known(prev_snap, platform_id):
    """(metrics dict, date) from the previous snapshot, or (None, None)."""
    if not prev_snap:
        return None, None
    entry = (prev_snap.get("platforms") or {}).get(platform_id)
    if not entry or entry.get("followers") is None:
        return None, None
    return entry, prev_snap["date"]


def carry_forward(p, prev_snap):
    """Couldn't scrape — reuse the last known numbers, flagged as reused."""
    prev_entry, prev_date = last_known(prev_snap, p["id"])
    if prev_entry:
        out = {k: v for k, v in prev_entry.items() if k not in ("source", "carried_from")}
        out["source"] = "carried"
        out["carried_from"] = prev_entry.get("carried_from", prev_date)
        return out
    return {"followers": None, "source": "carried"}


# ---------------------------------------------------------------- snapshots

def load_data():
    with open(DATA_FILE) as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def previous_snapshot(data, today):
    """Most recent snapshot from a DIFFERENT day (so a same-day rerun still
    compares against last week, not against itself)."""
    for snap in reversed(data["snapshots"]):
        if snap["date"] != today:
            return snap
    return None


def upsert_snapshot(data, snap):
    """Same-day rerun replaces that day's snapshot instead of duplicating it."""
    snaps = data["snapshots"]
    if snaps and snaps[-1]["date"] == snap["date"]:
        snaps[-1] = snap
    else:
        snaps.append(snap)
    snaps.sort(key=lambda s: s["date"])


# ---------------------------------------------------------------- output

def print_summary(snap, prev_snap, platforms):
    print()
    print("=" * 56)
    print("  SOMBA stats for %s" % snap["date"])
    print("=" * 56)
    total, prev_total, have_prev = 0, 0, False
    for p in platforms:
        entry = snap["platforms"].get(p["id"])
        if not entry:
            continue
        followers = entry.get("followers")
        prev_entry, _ = last_known(prev_snap, p["id"])
        delta = ""
        if followers is not None and prev_entry:
            diff = followers - prev_entry["followers"]
            delta = "%+d" % diff if diff else "no change"
            prev_total += prev_entry["followers"]
            have_prev = True
        stale = "  (reused old number)" if entry.get("source") == "carried" else ""
        shown = "?" if followers is None else "{:,}".format(followers)
        print("  %-10s %8s followers   %s%s" % (p["name"], shown, delta, stale))
        if followers is not None:
            total += followers
    print("-" * 56)
    line = "  Total audience: {:,}".format(total)
    if have_prev:
        line += "   (%+d since last update)" % (total - prev_total)
    print(line)
    print("=" * 56)


# ---------------------------------------------------------------- main

def main():
    data = load_data()
    platforms = [p for p in data["config"]["platforms"] if p.get("enabled")]
    today = date.today().isoformat()
    prev_snap = previous_snapshot(data, today)

    print("Fetching stats for %d platforms..." % len(platforms))
    snap = {"date": today, "platforms": {}}
    for p in platforms:
        sys.stdout.write("  %s... " % p["name"])
        sys.stdout.flush()
        try:
            metrics = FETCHERS[p["id"]](p)
            metrics["source"] = "scrape"
            print("ok (%s followers)" % "{:,}".format(metrics["followers"]))
        except Exception as e:
            metrics = carry_forward(p, prev_snap)
            note = "reused last number" if metrics.get("followers") is not None else "no data yet"
            print("could not read (%s) — %s" % (e, note))
        snap["platforms"][p["id"]] = metrics

    yt = next((p for p in platforms if p["id"] == "youtube" and p.get("channel_id")), None)
    if yt:
        sys.stdout.write("  Recent videos... ")
        sys.stdout.flush()
        try:
            vids = fetch_youtube_videos(yt["channel_id"])
            data["recent_videos"] = {"fetched": today, "source": "youtube-rss", "videos": vids}
            print("ok (%d videos)" % len(vids))
        except Exception as e:
            print("could not read (%s) — reused last list" % e)

    upsert_snapshot(data, snap)
    save_data(data)
    print_summary(snap, prev_snap, platforms)


if __name__ == "__main__":
    main()
