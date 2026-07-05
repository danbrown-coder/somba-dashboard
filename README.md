# SOMBA Social Media Dashboard

A one-page website showing follower growth for the Cal Lutheran School of
Management Brand Ambassador program (SOMBA) across Instagram, TikTok,
YouTube, and LinkedIn (Facebook slot ready for later).

How it works, in one sentence: **once a week you run one script on your Mac,
it collects the numbers, and pushing to GitHub updates the live site.**

---

## One-time setup (three steps, ~10 minutes total)

### Step 1 — Put the code on GitHub

GitHub is the website that stores the code. Render (the site host) watches it
and republishes the dashboard every time the code changes.

1. Go to <https://github.com/new>
2. Repository name: `somba-dashboard` · Public · do NOT add a README
3. Click **Create repository**
4. Then in Terminal, run (replace nothing — these are ready to paste):

```
cd ~/code/somba-dashboard
git remote add origin https://github.com/danbrown-coder/somba-dashboard.git
git push -u origin main
```

### Step 2 — Get a free YouTube API key (~2 minutes)

An API key is like a library card: it lets the script ask YouTube for the
channel's public numbers.

1. Go to <https://console.cloud.google.com> and sign in
2. At the top, select the project you made for the YouTube analytics setup
   (YouTube Data API v3 is already switched on there)
3. Left menu → **APIs & Services → Credentials**
4. **+ Create credentials → API key** — copy the long code it shows
5. Recommended: click the new key → **Restrict key** → under
   "API restrictions" choose **YouTube Data API v3** → Save

The first time you run the update script it asks for this key once, then
remembers it (saved in `.yt_api_key`, which never leaves your Mac).

### Step 3 — Create the live site on Render (~2 minutes)

1. Go to <https://dashboard.render.com>
2. **New → Static Site**
3. Connect the `somba-dashboard` GitHub repository
4. Publish directory: `.` (just a dot)
5. Click **Create Static Site**

Render gives you the public web address (something like
`somba-dashboard.onrender.com`). Every `git push` republishes it
automatically — same as the YouTube growth dashboard.

---

## The weekly routine (~2 minutes)

Double-click **`weekly-update.command`** in this folder
(or run `python3 update_stats.py` in Terminal). It will:

1. Fetch Instagram, TikTok, YouTube, and LinkedIn numbers
2. Ask you to type any number it couldn't fetch
   (press Enter to reuse last week's — the dashboard marks it as reused)
3. Show a summary of this week vs last week
4. Ask "Publish to the live site now?" — type `y` and you're done

Running it twice in one day is safe: the second run replaces that day's
numbers instead of duplicating them.

## Adding Facebook later

Open `data/stats.json` and in the Facebook entry set `"url"` to the page's
web address and `"enabled": true`. The script will then ask you to type the
Facebook follower count each week (Facebook doesn't allow automatic reading),
and the dashboard grows a Facebook card automatically.

## When something goes wrong

- **"Couldn't fetch X automatically"** — normal now and then; the platforms
  change their pages or temporarily block automated visitors (LinkedIn does
  this the most). Just type the number from the app, or press Enter to reuse
  last week's. If one platform fails every week for a month, ask Claude Code
  to update that platform's fetcher.
- **`CERTIFICATE_VERIFY_FAILED`** — your Python can't verify secure websites
  yet. In Finder go to Applications → Python 3.x → double-click
  **Install Certificates.command**, then rerun.
- **`git push` asks who you are / fails** — run the two lines it suggests, or
  ask Claude Code for help.
- **YouTube numbers look rounded** (e.g. exactly 1,230) — YouTube rounds
  subscriber counts for bigger channels; that's them, not a bug.

## Files in this folder

| File | What it is |
|---|---|
| `index.html` | The dashboard page people see |
| `update_stats.py` | The weekly script that collects the numbers |
| `data/stats.json` | The numbers themselves — every weekly snapshot lives here |
| `weekly-update.command` | Double-clickable shortcut for the weekly routine |
| `.yt_api_key` | Your YouTube API key (stays on your Mac, never uploaded) |
