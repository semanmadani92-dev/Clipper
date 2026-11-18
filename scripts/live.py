"""Clip Twitch streams while they are still live.

Viewers clip the best moments of a live stream within minutes, and each clip
can be downloaded straight away.  This watches a category (or channels) for
the most-viewed recent clips from streams that are live right now, downloads
the new ones and turns each into a viral-format short with clip.py --whole.

Usage:
    python scripts/live.py --game "Grand Theft Auto VI" -n 3 --out out/live
    python scripts/live.py --game "Grand Theft Auto VI" --every 15     # keep watching
    python scripts/live.py --channel xqc --channel lacy -n 2

Processed clips are remembered in OUT/seen.json, so repeated runs only make
shorts from new moments.
"""
import argparse, datetime, json, re, subprocess, sys, time, urllib.request
from pathlib import Path

GQL_URL = "https://gql.twitch.tv/gql"
GQL_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
HERE = Path(__file__).resolve().parent
CLIP_FIELDS = ("slug url title viewCount durationSeconds createdAt language "
               "broadcaster{login displayName stream{id}}")


def gql(query):
    req = urllib.request.Request(GQL_URL, json.dumps({"query": query}).encode(), {
        "Client-Id": GQL_CLIENT_ID, "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            r = json.load(urllib.request.urlopen(req, timeout=30))
            if r.get("errors"):
                raise RuntimeError(r["errors"][0].get("message"))
            return r["data"]
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1.5 * 2 ** attempt)


def recent_clips(game=None, channels=(), lang="EN"):
    out = []
    if game:
        d = gql(f'query{{game(name:{json.dumps(game)}){{clips(first:100, criteria:{{period:LAST_DAY, '
                f'sort:VIEWS_DESC, languages:[{lang}]}}){{edges{{node{{{CLIP_FIELDS}}}}}}}}}}}')
        out += [e["node"] for e in ((d.get("game") or {}).get("clips") or {}).get("edges", [])]
    for ch in channels:
        d = gql(f'query{{user(login:{json.dumps(ch)}){{clips(first:50, criteria:{{period:LAST_DAY, '
                f'sort:VIEWS_DESC}}){{edges{{node{{{CLIP_FIELDS}}}}}}}}}}}')
        out += [e["node"] for e in ((d.get("user") or {}).get("clips") or {}).get("edges", [])]
    return out


def hook_for(clip):
    """Viewer titles are often 'wtf' or 'LUCIA'; fall back to the streamer's name."""
    title = re.sub(r"\s+", " ", clip["title"]).strip()
    name = clip["broadcaster"]["displayName"]
    if len(title.split()) >= 3 and len(title) <= 70:
        return title if name.lower() in title.lower() else f"{name}: {title}"
    return f"{name} {title}".strip() if title else name


def run_once(args, out, seen):
    now = datetime.datetime.now(datetime.timezone.utc)
    picks, used = [], set()
    clips = recent_clips(args.game, args.channel or (), args.lang)
    for c in sorted(clips, key=lambda c: -c["viewCount"]):
        made = datetime.datetime.fromisoformat(c["createdAt"].replace("Z", "+00:00"))
        who = c["broadcaster"]["login"]
        if c["slug"] in seen or who in used:
            continue  # one short per streamer per round keeps the batch varied
        if (now - made).total_seconds() > args.hours * 3600 or c["viewCount"] < args.min_views:
            continue
        if args.live_only and not (c["broadcaster"] or {}).get("stream"):
            continue
        picks.append(c)
        used.add(who)
        if len(picks) >= args.n:
            break
    print(f"{len(clips)} clips scanned, {len(picks)} new picks", flush=True)
    for c in picks:
        who = c["broadcaster"]["login"]
        stem = re.sub(r"[^a-z0-9]+", "_", f"{who}_{c['title']}".lower()).strip("_")[:60]
        raw = out / "raw" / f"{c['slug']}.mp4"
        raw.parent.mkdir(parents=True, exist_ok=True)
        if not raw.exists():
            subprocess.run(["yt-dlp", "-q", "-f", "best[height<=1080]", "-o", str(raw), c["url"]], check=True)
        hook = hook_for(c)
        print(f"-> {who}: {c['viewCount']:,} views  hook={hook!r}", flush=True)
        subprocess.run([sys.executable, str(HERE / "clip.py"), str(raw), "--whole", "--hook", hook,
                        "--name", stem, "--out", str(out)], check=True)
        seen[c["slug"]] = {"file": f"{stem}.mp4", "streamer": who, "views": c["viewCount"],
                           "title": c["title"], "hook": hook, "url": c["url"], "made": now.isoformat()}
        (out / "seen.json").write_text(json.dumps(seen, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", help='Twitch category, e.g. "Grand Theft Auto VI"')
    ap.add_argument("--channel", action="append", help="watch these channels (repeatable)")
    ap.add_argument("-n", type=int, default=3, help="shorts per round")
    ap.add_argument("--hours", type=float, default=3, help="only clips made in the last N hours")
    ap.add_argument("--min-views", type=int, default=500)
    ap.add_argument("--lang", default="EN")
    ap.add_argument("--live-only", action=argparse.BooleanOptionalAction, default=True,
                    help="only streams that are live right now (default on)")
    ap.add_argument("--every", type=float, default=0, help="repeat every N minutes (0 = once)")
    ap.add_argument("--out", default="out/live")
    args = ap.parse_args()
    if not args.game and not args.channel:
        ap.error("give --game and/or --channel")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    seen_path = out / "seen.json"
    seen = json.loads(seen_path.read_text()) if seen_path.exists() else {}
    while True:
        run_once(args, out, seen)
        if not args.every:
            break
        time.sleep(args.every * 60)


if __name__ == "__main__":
    sys.exit(main())
