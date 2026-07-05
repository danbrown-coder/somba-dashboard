#!/usr/bin/env python3
"""SOMBA weekly stats updater.

Run this once a week:  python3 update_stats.py
It fetches follower counts for every enabled platform in data/stats.json,
asks you to type any number it can't fetch, saves a dated snapshot, and
offers to publish (git push) so the live dashboard updates.

Uses only Python's standard library — nothing to install.
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(REPO_DIR, "data", "stats.json")
KEY_FILE = os.path.join(REPO_DIR, ".yt_api_key")

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


def ask(prompt):
    """input() that survives non-interactive runs (returns '' at EOF)."""
    try:
        return input(prompt)
    except EOFError:
        print()
        return ""


def get_api_key():
    """Read the saved YouTube API key, or ask for it once and remember it."""
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE) as f:
            key = f.read().strip()
        if key:
            return key
    print()
    print("YouTube needs a free API key (see README.md, step 2 — takes ~2 minutes).")
    key = ask("Paste your YouTube API key (or press Enter to skip YouTube this week): ").strip()
    if key:
        with open(KEY_FILE, "w") as f:
            f.write(key + "\n")
        os.chmod(KEY_FILE, 0o600)
        print("Saved — you won't be asked again.")
    return key


# ---------------------------------------------------------------- fetchers
# Each fetcher returns a dict of metrics including "followers",
# or raises an exception (which triggers the type-it-in fallback).

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


def fetch_youtube(p, api_key):
    if not api_key:
        raise RuntimeError("no API key")
    url = (
        "https://www.googleapis.com/youtube/v3/channels"
        "?part=statistics&id=%s&key=%s" % (p["channel_id"], api_key)
    )
    body = json.loads(http_get(url, CHROME_UA))
    items = body.get("items") or []
    if not items:
        raise RuntimeError("channel not found (check channel_id in data/stats.json)")
    stats = items[0]["statistics"]
    return {
        "followers": int(stats.get("subscriberCount", 0)),
        "views": int(stats.get("viewCount", 0)),
        "videos": int(stats.get("videoCount", 0)),
    }


def fetch_linkedin(p):
    html = http_get(p["url"], CHROME_UA)
    m = re.search(r'([\d.,]+[KM]?)\s+followers', html, re.IGNORECASE)
    if not m:
        raise RuntimeError("follower count not found in the LinkedIn page")
    return {"followers": parse_abbrev(m.group(1))}


def fetch_facebook(p):
    raise RuntimeError("Facebook has no automatic fetch — numbers are typed in manually")


FETCHERS = {
    "instagram": fetch_instagram,
    "tiktok": fetch_tiktok,
    "linkedin": fetch_linkedin,
    "facebook": fetch_facebook,
}


# ---------------------------------------------------------------- fallback

def last_known(prev_snap, platform_id):
    """(metrics dict, date) from the previous snapshot, or (None, None)."""
    if not prev_snap:
        return None, None
    entry = (prev_snap.get("platforms") or {}).get(platform_id)
    if not entry or entry.get("followers") is None:
        return None, None
    return entry, prev_snap["date"]


def manual_fallback(p, reason, prev_snap):
    """Couldn't fetch — ask for the follower count, or reuse the last one."""
    prev_entry, prev_date = last_known(prev_snap, p["id"])
    print()
    print("  Couldn't fetch %s automatically (%s)." % (p["name"], reason))
    if prev_entry:
        hint = "or press Enter to reuse %s from %s" % (prev_entry["followers"], prev_date)
    else:
        hint = "or press Enter to skip"
    while True:
        raw = ask("  Type the current %s follower count (%s): " % (p["name"], hint)).strip()
        if not raw:
            if prev_entry:
                # Carry everything forward, flagged as stale.
                out = {k: v for k, v in prev_entry.items() if k not in ("source", "carried_from")}
                out["source"] = "carried"
                out["carried_from"] = prev_entry.get("carried_from", prev_date)
                return out
            return {"followers": None, "source": "manual"}
        try:
            return {"followers": parse_abbrev(raw), "source": "manual"}
        except ValueError:
            print("  That doesn't look like a number — try again (e.g. 756 or 13.8K).")


# ---------------------------------------------------------------- snapshots

def load_data():
    with open(DATA_FILE) as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def previous_snapshot(data, today):
    """Most recent snapshot from a DIFFERENT day (so a same-day rerun
    still compares against last week, not against itself)."""
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


def offer_git_push(today):
    print()
    answer = ask("Publish to the live site now? [y/N]: ").strip().lower()
    if answer != "y":
        print()
        print("Okay — when you're ready, run:")
        print('  cd "%s" && git add data/stats.json && git commit -m "Weekly stats %s" && git push' % (REPO_DIR, today))
        return
    cmds = [
        ["git", "add", "data/stats.json"],
        ["git", "commit", "-m", "Weekly stats %s" % today],
        ["git", "push"],
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, cwd=REPO_DIR)
        if result.returncode != 0:
            print()
            print("That git step failed (see message above). Nothing is lost —")
            print("your numbers are saved in data/stats.json. Fix the issue and rerun,")
            print("or ask Claude Code for help.")
            return
    print()
    print("Published! Render redeploys in about a minute.")


# ---------------------------------------------------------------- main

def main():
    data = load_data()
    platforms = [p for p in data["config"]["platforms"] if p.get("enabled")]
    today = date.today().isoformat()
    prev_snap = previous_snapshot(data, today)

    api_key = get_api_key() if any(p["id"] == "youtube" for p in platforms) else ""

    print()
    print("Fetching stats for %d platforms..." % len(platforms))
    snap = {"date": today, "platforms": {}}
    for p in platforms:
        sys.stdout.write("  %s... " % p["name"])
        sys.stdout.flush()
        try:
            if p["id"] == "youtube":
                metrics = fetch_youtube(p, api_key)
                metrics["source"] = "api"
            else:
                metrics = FETCHERS[p["id"]](p)
                metrics["source"] = "scrape"
            print("ok (%s followers)" % "{:,}".format(metrics["followers"]))
        except Exception as e:
            print("failed")
            metrics = manual_fallback(p, str(e), prev_snap)
        snap["platforms"][p["id"]] = metrics

    upsert_snapshot(data, snap)
    save_data(data)
    print_summary(snap, prev_snap, platforms)
    offer_git_push(today)


if __name__ == "__main__":
    main()
