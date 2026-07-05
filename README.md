# SOMBA Social Media Dashboard

A one-page website showing follower growth for the Cal Lutheran School of
Management Brand Ambassador program (SOMBA) across Instagram, TikTok,
YouTube, and LinkedIn (Facebook slot ready for later).

**It runs itself.** Every Monday a free automation reads the latest follower
counts and publishes them. No API keys, no logins, no numbers to type,
nothing to run. You never have to touch it.

---

## How it works (so you know, not because you need to do anything)

1. A scheduled job on GitHub (called a "GitHub Action") wakes up every Monday.
2. It reads the public follower counts from each platform's page.
3. It saves them into `data/stats.json` and commits that change.
4. Render sees the change and republishes the live site automatically.

If a platform can't be read one week (they occasionally block automated
visitors — LinkedIn most often), that platform simply keeps last week's
number and the card shows a small "reused" note. The dashboard never breaks.

---

## The only one-time setup: connect it to Render

This is the single human step, and it's a few clicks:

1. Go to <https://dashboard.render.com>
2. **New → Static Site**
3. Connect the **somba-dashboard** GitHub repository
4. **Publish directory**: type a single dot — `.`
5. Leave **Build Command** blank
6. Click **Create Static Site**

Render gives you the public web address (like `somba-dashboard.onrender.com`).
From then on it updates on its own.

---

## Want to refresh it right now instead of waiting for Monday?

Two easy ways, both optional:

- **On GitHub**: open the repo → **Actions** tab → **Update SOMBA stats** →
  **Run workflow**. It fetches fresh numbers and republishes in about a minute.
- **On your Mac**: double-click **`weekly-update.command`** in this folder.

## What the dashboard shows

- **Total audience** — everyone following SOMBA anywhere, added together
- **Platform cards** — followers per platform with week-over-week change
- **Follower growth charts** — one per platform (appear after two weeks of data)
- **Growth pace** — new followers per week, fastest-growing platform, and a
  milestone projection ("Instagram passes 1,000 followers by ~…")
- **Engagement** — likes per follower, average views per video, total content
  published
- **Recent content** — the latest YouTube uploads ranked by views (pulled from
  YouTube's official public feed)
- **Audience mix** — a donut chart of which platform holds how much of the
  audience
- **Who we reach** — age, gender, and location breakdown. **Right now these
  are illustrative estimates** (the section's note line says so) because
  platforms only show real demographics to the account owner inside their
  apps. See below for swapping in the real numbers.
- **Growth strategy** — the overall playbook (film once → post to TikTok,
  Reels, and Shorts) plus a per-platform breakdown of each channel's job
  and next moves.

## Replacing the estimated demographics with real numbers

The age/gender/location numbers are placeholders until someone with access to
the SOMBA accounts copies the real ones from the apps (about 10 minutes):

1. In the Instagram app: **Professional dashboard → Total followers** shows
   age ranges, gender, and top cities. TikTok: **Profile → TikTok Studio →
   Analytics → Followers** shows the same.
2. Open `data/stats.json` in any text editor and find `"demographics"`.
3. Overtype the `pct` numbers with the real ones (each group should add up
   to about 100).
4. Change `"estimated": true` to `"estimated": false` and update `"as_of"`
   to today's date.
5. Save, then publish: double-click `weekly-update.command`, or ask
   Claude Code to push. The gold "Estimated" badge disappears on its own.

## Adding Facebook later

Open `data/stats.json`, find the Facebook entry, set its `"url"` to the page
address and `"enabled": true`. Facebook doesn't allow automatic reading, so it
will just show whatever number was last recorded — but the card appears and
you can update `data/stats.json` by hand whenever you like.

## If a number ever looks stuck

A platform showing a "reused" note for several weeks means its page stopped
letting the automation read it. Ask Claude Code to update that platform's
reader — it's a small fix in `update_stats.py`.

## Files in this folder

| File | What it is |
|---|---|
| `index.html` | The dashboard page people see |
| `data/stats.json` | The numbers — every weekly snapshot lives here |
| `update_stats.py` | The scraper that collects the numbers |
| `.github/workflows/update-stats.yml` | The Monday automation |
| `weekly-update.command` | Optional double-click "refresh now" button |
