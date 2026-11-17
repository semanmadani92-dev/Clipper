"""Find Twitch streams (VODs) that are worth clipping right now.

A stream whose clips are racking up views is a proven source of moments, so
this scans the most-watched categories for their most-viewed clips of the
last day/week, groups the clips by the VOD they came from, and ranks VODs by
total clip views.  Clips whose VOD is gone (deleted / sub-only / expired)
are skipped, since clip.py needs the VOD.

Usage:
    python scripts/discover.py [--period day|week] [--games 12] [--lang EN] [--top 15]
    python scripts/discover.py --game "Just Chatting" --game Fortnite

Then feed a result to clip.py:
    python scripts/clip.py https://www.twitch.tv/videos/<id> --candidates 8 --out out/
"""
import argparse, json, sys, time, urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

GQL_URL = "https://gql.twitch.tv/gql"
GQL_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
PERIOD = {"day": "LAST_DAY", "week": "LAST_WEEK"}


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


def top_games(n):
    d = gql(f"query{{games(first:{n}){{edges{{node{{name viewersCount}}}}}}}}")
    return [e["node"]["name"] for e in d["games"]["edges"]]


def game_clips(game, period, lang, pages=1):
    """Most-viewed clips in a category (100 per page).  Twitch's integrity
    check tends to refuse deeper paging, so one page is the default and a
    refused category is skipped rather than failing the whole scan."""
    out, after = [], None
    name = json.dumps(game)
    for _ in range(pages):
        cur = f', after:"{after}"' if after else ""
        try:
            d = gql(f'query{{game(name:{name}){{clips(first:100{cur}, criteria:{{period:{period}, '
                    f'sort:VIEWS_DESC, languages:[{lang}]}}){{edges{{cursor node{{title viewCount '
                    f'durationSeconds videoOffsetSeconds broadcaster{{login displayName}} '
                    f'video{{id lengthSeconds createdAt title}}}}}} pageInfo{{hasNextPage}}}}}}}}')
        except Exception as e:
            print(f"  skipped {game}: {e}", file=sys.stderr)
            break
        c = (d.get("game") or {}).get("clips")
        if not c:
            break
        for e in c["edges"]:
            out.append({**e["node"], "game": game})
        if not c["pageInfo"]["hasNextPage"] or not c["edges"]:
            break
        after = c["edges"][-1]["cursor"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", choices=sorted(PERIOD), default="day")
    ap.add_argument("--games", type=int, default=12, help="scan this many top categories")
    ap.add_argument("--game", action="append", help="scan these categories instead (repeatable)")
    ap.add_argument("--lang", default="EN")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--min-clips", type=int, default=2, help="ignore VODs with fewer viewer clips")
    ap.add_argument("--json", help="also write the ranking here")
    args = ap.parse_args()

    games = args.game or top_games(args.games)
    with ThreadPoolExecutor(3) as ex:
        clips = [c for cs in ex.map(lambda g: game_clips(g, PERIOD[args.period], args.lang), games) for c in cs]

    vods = defaultdict(lambda: {"clips": []})
    for c in clips:
        v = c.get("video")
        if not v or c.get("videoOffsetSeconds") is None:
            continue  # VOD unavailable: nothing to download
        g = vods[v["id"]]
        g.update(vod=v["id"], channel=c["broadcaster"]["login"], game=c["game"],
                 vod_title=v.get("title"), length_h=round((v.get("lengthSeconds") or 0) / 3600, 1),
                 created=(v.get("createdAt") or "")[:10])
        g["clips"].append({"views": c["viewCount"], "title": c["title"],
                           "at": c["videoOffsetSeconds"], "dur": c["durationSeconds"]})
    ranked = []
    for g in vods.values():
        if len(g["clips"]) < args.min_clips:
            continue
        g["clips"].sort(key=lambda c: -c["views"])
        g["clip_views"] = sum(c["views"] for c in g["clips"])
        g["n_clips"] = len(g["clips"])
        g["url"] = f"https://www.twitch.tv/videos/{g['vod']}"
        ranked.append(g)
    ranked.sort(key=lambda g: -g["clip_views"])
    ranked = ranked[:args.top]

    print(f"scanned {len(games)} categories, {len(clips)} clips -> {len(vods)} VODs available\n")
    for i, g in enumerate(ranked, 1):
        print(f"{i:2}. {g['channel']:<18} {g['game'][:18]:<18} {g['clip_views']:>7,} views "
              f"in {g['n_clips']:>2} clips  {g['length_h']}h  {g['created']}  {g['url']}")
        for c in g["clips"][:3]:
            print(f"      {c['views']:>6,}  {c['title'][:70]}")
    if args.json:
        with open(args.json, "w") as f:
            json.dump(ranked, f, indent=2)


if __name__ == "__main__":
    sys.exit(main())
