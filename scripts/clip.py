"""Clip a long video into 9:16 vertical shorts with word-by-word captions.

Usage:
    python scripts/clip.py SOURCE [--chat CHAT.json] [-n 3] [--out out/]

    # Twitch, editor-in-the-loop (the editor can be a person or an LLM):
    python scripts/clip.py TWITCH_VOD_URL --candidates 8 --out out/   # -> out/candidates.json
    #   read the transcripts, write plan.json:
    #   [{"id": 3, "name": "slug", "start": 5177.0, "end": 5221.0,
    #     "hook": "Speed's friend tries to expose him", "teaser": [5203.4, 5206.1]}]
    python scripts/clip.py TWITCH_VOD_URL --plan plan.json --out out/

SOURCE is a local video file or a URL (yt-dlp).

Viral format (default; --plain turns it off): hook title in a white box
(top, or a title bar across the cam/gameplay seam), Anton captions with the
active word popping in, punch-in zooms on the loudest reactions, a progress
bar, and an optional cold-open teaser of the payoff.  On Twitch the
streamer is recognised by face (the identity present in most moments) so
multi-cam squad layouts keep the right person on top.

Moment selection:
  * Twitch VOD URL: chat replay is pulled straight from Twitch's public GraphQL
    API.  The whole VOD is sampled every 10 s in parallel (rate of unique
    chatters + emote reactions), the top spikes are picked by robust z-score
    against a trailing 5 min baseline, then every message around each spike
    is paged in to pin the peak to the second.  Only the clip sections are
    downloaded (start 30 s before the peak, end 15 s after), so multi-hour
    VODs are fine.
  * --chat CHAT.json with a local file: same spike logic on a saved chat log.
  * URL whose metadata has YouTube's "Most replayed" heatmap: the top heatmap
    segments, section-downloaded.
  * Otherwise: audio excitement (loudness z-score, boosted by speech rate and
    shouty transcript words).  Each clip runs ~20 s before to ~15 s after the
    peak, snapped to sentence boundaries.

Framing (OpenCV face detection on sampled frames of each clip):
  * a small, stationary face in a corner  -> facecam stacked over gameplay
  * otherwise                              -> full-height 9:16 crop centred on
                                              the median face position (or the
                                              frame centre when there is none)

Silence: wordless pauses >= 0.4 s that sit 12 dB+ below the speech level are
jump-cut out (--keep-silence to disable); captions are re-timed to match.

Captions: faster-whisper word timestamps -> ASS, 3-word pages, active word
scaled up and coloured, cycling yellow/green/cyan/pink/orange per page
(--captions yellow for a single colour), burned in with libass.
"""
import argparse, calendar, json, os, re, subprocess, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

FONT = "DejaVu Sans"
REACT = {"KEKW": 2.0, "LUL": 1.5, "LULW": 1.5, "OMEGALUL": 2.0, "Pog": 1.5, "PogChamp": 1.5,
         "POGGERS": 1.5, "W": 1.0, "L": 1.0, "monkaS": 1.0, "Clip": 3.0, "CLIP": 3.0, "LMAO": 1.5}


def sh(cmd, **kw):
    print("+", " ".join(map(str, cmd))[:200], flush=True)
    return subprocess.run(list(map(str, cmd)), check=True, **kw)


def probe_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def probe_size(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, check=True)
    w, h = r.stdout.strip().split(",")[:2]
    return int(w), int(h)


# ---------------------------------------------------------------- acquisition
FMT = "bv*[height<=1080]+ba/b[height<=1080]/b"


def twitch_vod_id(src):
    m = re.search(r"twitch\.tv/(?:videos/|\w+/v/)(\d+)", src)
    return m.group(1) if m else None


def ytdlp_proxy_args():
    # yt-dlp honours HTTPS_PROXY itself, but the ffmpeg it spawns for section
    # downloads does not; hand the proxy to ffmpeg explicitly when there is one.
    p = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    return ["--downloader-args", f"ffmpeg_i:-http_proxy {p}"] if p else []


def ytdlp_info(url):
    r = subprocess.run(["yt-dlp", "-J", "--no-playlist", "--skip-download", url],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def fetch(src, work):
    if Path(src).exists():
        return Path(src)
    out = work / "source.%(ext)s"
    sh(["yt-dlp", "--no-playlist", "-f", FMT, "--merge-output-format", "mp4", "-o", out, src])
    return next(work.glob("source.*"))


def download_section(url, s, e, path):
    if path.exists():
        return path
    sh(["yt-dlp", "--no-playlist", "-f", FMT, "--download-sections", f"*{s:.2f}-{e:.2f}",
        "--merge-output-format", "mp4", *ytdlp_proxy_args(), "-o", path, url])
    return path


# Twitch chat replay via the public GraphQL endpoint the web player uses.
GQL_URL = "https://gql.twitch.tv/gql"
GQL_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
GQL_COMMENTS_HASH = "b70a3591ff0f4e0313d126c6a1502d79a1c02baebb288227c582044aa76adf6a"


def gql_comments(vod, offset=None, cursor=None):
    """One page (~50 msgs) of chat: ([(t, user, text)], next_cursor or None)."""
    var = {"videoID": vod}
    if cursor:
        var["cursor"] = cursor
    else:
        var["contentOffsetSeconds"] = int(offset)
    body = json.dumps([{"operationName": "VideoCommentsByOffsetOrCursor", "variables": var,
                        "extensions": {"persistedQuery": {"version": 1, "sha256Hash": GQL_COMMENTS_HASH}}}])
    for attempt in range(5):
        try:
            req = urllib.request.Request(GQL_URL, body.encode(), {
                "Client-Id": GQL_CLIENT_ID, "Content-Type": "application/json"})
            data = json.load(urllib.request.urlopen(req, timeout=20))[0]["data"]["video"]["comments"]
            break
        except Exception:
            if attempt == 4:
                raise
            time.sleep(1.5 * 2 ** attempt)
    if not data:
        return [], None
    msgs = []
    for edge in data["edges"]:
        n = edge["node"]
        text = "".join(f.get("text", "") for f in (n.get("message") or {}).get("fragments") or [])
        user = (n.get("commenter") or {}).get("login", "?")
        msgs.append((float(n["contentOffsetSeconds"]), user, text))
    nxt = data["edges"][-1]["cursor"] if data["edges"] and data["pageInfo"]["hasNextPage"] else None
    return msgs, nxt


def gql_query(query):
    req = urllib.request.Request(GQL_URL, json.dumps({"query": query}).encode(), {
        "Client-Id": GQL_CLIENT_ID, "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            r = json.load(urllib.request.urlopen(req, timeout=20))
            if r.get("errors"):
                raise RuntimeError(r["errors"][0].get("message"))
            return r["data"]
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1.5 * 2 ** attempt)


def twitch_clip_moments(vod, dur, n, max_pages=10, max_len=75):
    """Moments viewers clipped from this VOD, ranked by total clip views.

    Clips of the same moment (overlapping VOD ranges) are merged; each window
    is the viewers' own range plus a 2 s lead-in, trimmed around the most-viewed
    clip when the merged range gets too long."""
    meta = gql_query(f'query{{video(id:"{vod}"){{createdAt owner{{login}}}}}}')["video"]
    login = meta["owner"]["login"]
    age_days = (time.time() - calendar.timegm(time.strptime(meta["createdAt"][:19], "%Y-%m-%dT%H:%M:%S"))) / 86400
    period = "LAST_WEEK" if age_days < 6.5 else "LAST_MONTH" if age_days < 29 else "ALL_TIME"
    clips, after = [], None
    for _ in range(max_pages):
        cur = f', after:"{after}"' if after else ""
        d = gql_query(f'query{{user(login:"{login}"){{clips(first:100{cur}, criteria:{{period:{period}, '
                      f'sort:VIEWS_DESC}}){{edges{{cursor node{{title viewCount durationSeconds '
                      f'videoOffsetSeconds video{{id}}}}}} pageInfo{{hasNextPage}}}}}}}}')
        c = d["user"]["clips"]
        for edge in c["edges"]:
            nd = edge["node"]
            if (nd.get("video") or {}).get("id") == vod and nd.get("videoOffsetSeconds") is not None:
                clips.append(nd)
        if not c["pageInfo"]["hasNextPage"] or not c["edges"] or c["edges"][-1]["node"]["viewCount"] < 20:
            break
        after = c["edges"][-1]["cursor"]
    groups = []
    for cl in sorted(clips, key=lambda c: c["videoOffsetSeconds"]):
        a = float(cl["videoOffsetSeconds"])
        b = a + float(cl["durationSeconds"])
        if groups and a < groups[-1]["b"] - 5:
            g = groups[-1]
            g["b"] = max(g["b"], b)
            g["clips"].append(cl)
        else:
            groups.append({"a": a, "b": b, "clips": [cl]})
    moments = []
    for g in groups:
        top = max(g["clips"], key=lambda c: c["viewCount"])
        a, b = g["a"], g["b"]
        if b - a > max_len:
            a = float(top["videoOffsetSeconds"])
            b = a + float(top["durationSeconds"])
        views = sum(c["viewCount"] for c in g["clips"])
        moments.append({"s": max(0.0, a - 2), "e": min(dur, b + 1), "p": (a + b) / 2,
                        "score": views, "views": views, "clippers": len(g["clips"]),
                        "title": top["title"], "mode": "viewer-clips"})
    moments.sort(key=lambda m: -m["views"])
    return moments[:n]


def react_score(text):
    return sum(REACT.get(tok, 0) for tok in text.split())


def twitch_chat_profile(vod, dur, work, step=10, workers=16):
    """Per-second chat score for the whole VOD from one chat page every `step` s."""
    cache = work / f"chat_profile_{vod}_{step}.json"
    if cache.exists():
        samples = json.loads(cache.read_text())
    else:
        offsets = list(range(0, int(dur), step))

        def sample(off):
            msgs, _ = gql_comments(vod, offset=off)
            msgs = [m for m in msgs if m[0] >= off - 1]
            if not msgs:
                return [off, 0.0, 0.0]
            span = max(msgs[-1][0] - msgs[0][0], 1.0)
            return [off, len({u for _, u, _ in msgs}) / span, sum(react_score(t) for *_, t in msgs) / span]

        t0 = time.time()
        with ThreadPoolExecutor(workers) as ex:
            samples = list(ex.map(sample, offsets))
        print(f"  chat: sampled {len(samples)} points in {time.time() - t0:.0f}s", flush=True)
        cache.write_text(json.dumps(samples))
    s = np.array(samples, float)
    grid = np.arange(int(dur) + 1)
    W = 10  # same scale as "unique chatters per 10 s"
    return np.interp(grid, s[:, 0], W * s[:, 1] + 0.3 * W * s[:, 2])


def twitch_refine_peak(vod, p, before=40, after=25, max_pages=400):
    """Page every message in [p-before, p+after] and return the busiest second."""
    msgs, cur = gql_comments(vod, offset=max(0, p - before))
    pages = 1
    while cur and msgs and msgs[-1][0] < p + after and pages < max_pages:
        more, cur = gql_comments(vod, cursor=cur)
        msgs += more
        pages += 1
    lo = max(0, p - before)
    local = [(t - lo, u, x) for t, u, x in msgs if lo <= t <= p + after]
    if not local:
        return p
    sc = chat_scores(local, before + after)
    return int(lo + int(np.argmax(sc)))


def load_chat(path):
    """Return [(t_seconds, user, text)] from chat-downloader or TwitchDownloader JSON."""
    raw = json.loads(Path(path).read_text())
    msgs = raw["comments"] if isinstance(raw, dict) and "comments" in raw else raw
    out = []
    for m in msgs:
        if "content_offset_seconds" in m:  # TwitchDownloader
            out.append((float(m["content_offset_seconds"]), m["commenter"]["name"], m["message"]["body"]))
        elif "time_in_seconds" in m:  # chat-downloader
            out.append((float(m["time_in_seconds"]), (m.get("author") or {}).get("name", "?"), m.get("message", "")))
    return out


# ---------------------------------------------------------------- scoring
def robust_z(score, warm=30, base_win=300, gap=10):
    z = np.zeros_like(score)
    for i in range(len(score)):
        base = score[max(0, i - base_win):max(1, i - gap)]
        med = np.median(base)
        mad = max(np.median(np.abs(base - med)) * 1.4826, 1e-6 + 0.05 * abs(med), 1e-3)
        z[i] = (score[i] - med) / mad
    z[:warm] = np.minimum(z[:warm], 0)
    return z


def pick_peaks(z, n, min_gap, dur, pre, post, thresh=2.0):
    order = np.argsort(-z)
    peaks = []
    for i in order:
        if z[i] < thresh or len(peaks) >= n:
            break
        if i - pre < 0 or i + post > dur:
            continue
        if all(abs(i - p) > min_gap for p in peaks):
            peaks.append(int(i))
    return sorted(peaks)


def chat_scores(chat, dur):
    D = int(dur) + 1
    users = [set() for _ in range(D)]
    react = np.zeros(D)
    for t, u, text in chat:
        s = int(t)
        if 0 <= s < D:
            users[s].add(u)
            react[s] += react_score(text)
    W = 10
    uniq = np.array([len(set().union(*users[max(0, i - W + 1):i + 1])) for i in range(D)], float)
    return uniq + 0.3 * np.convolve(react, np.ones(W), "full")[:D]


def audio_loudness(src, work):
    """Per-second RMS loudness in dB from a 16 kHz mono decode."""
    wav = work / "audio16k.f32"
    if not wav.exists():
        sh(["ffmpeg", "-y", "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", wav])
    a = np.fromfile(wav, dtype=np.float32)
    n = len(a) // 16000
    rms = np.sqrt(np.mean(a[:n * 16000].reshape(n, 16000) ** 2, axis=1) + 1e-10)
    return 20 * np.log10(rms)


def audio_scores(loud_db, words, dur):
    D = len(loud_db)
    loud = np.convolve(loud_db, np.ones(5) / 5, "same")
    rate = np.zeros(D)
    shout = np.zeros(D)
    for w in words:
        s = int(w["start"])
        if 0 <= s < D:
            rate[s] += 1
            txt = w["word"].strip()
            if txt.endswith("!") or (len(txt) > 2 and txt.isupper()):
                shout[s] += 1
    rate = np.convolve(rate, np.ones(5) / 5, "same")
    shout = np.convolve(shout, np.ones(5), "same")
    return loud + 1.5 * rate + 2.0 * shout


# ---------------------------------------------------------------- transcription
HALLUCINATION = re.compile(
    r"thanks? (you )?(so much )?for watching|like and subscribe|subscribe to (my|the|our) channel|"
    r"see you (in the )?next (video|time)|don'?t forget to (like|subscribe)|"
    r"subtitles? (by|provided)|transcri(bed|ption) by|amara\.org", re.I)
def transcribe(src, work, model_size, start=0.0, end=None):
    """Word list [{start,end,word}] in source time.  Cached per range."""
    key = f"v2_{Path(src).stem}_{model_size}_{start:.0f}_{end if end is None else round(end)}"
    cache = work / f"words_{key}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    # decode with ffmpeg ourselves (faster-whisper's PyAV path breaks on some av versions)
    cmd = ["ffmpeg", "-v", "error", "-ss", start]
    if end is not None:
        cmd += ["-to", end]
    raw = sh(cmd + ["-i", src, "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
             capture_output=True).stdout
    audio = np.frombuffer(raw, dtype=np.float32)
    segs, info = model.transcribe(audio, word_timestamps=True, vad_filter=True,
                                  condition_on_previous_text=False)
    words = []
    for seg in segs:
        # Whisper invents stock phrases over music/noise ("thanks for watching",
        # "like and subscribe"); drop those and segments it isn't confident are speech.
        if HALLUCINATION.search(seg.text) or (seg.no_speech_prob > 0.6 and seg.avg_logprob < -0.8):
            print(f"  dropped likely hallucination: {seg.text.strip()[:80]!r}", flush=True)
            continue
        for w in seg.words or []:
            words.append({"start": w.start + start, "end": w.end + start, "word": w.word,
                          "seg_start": seg.start + start, "seg_end": seg.end + start})
    print(f"  transcribed {len(words)} words (lang={info.language})", flush=True)
    cache.write_text(json.dumps(words))
    return words


def snap(words, t, direction, limit):
    """Move t to the nearest sentence/segment boundary within `limit` seconds."""
    bounds = sorted({w["seg_start"] for w in words} | {w["seg_end"] for w in words})
    cands = [b for b in bounds if abs(b - t) <= limit and ((direction < 0 and b <= t) or (direction > 0 and b >= t))]
    if not cands:
        return t
    return min(cands, key=lambda b: abs(b - t))


# ---------------------------------------------------------------- framing
_FACE = None


_REC = None


def _hf(repo, name):
    from huggingface_hub import hf_hub_download
    return hf_hub_download(repo, name)


def detect_faces(frame, rows=False):
    """YuNet face detector (OpenCV 5 dropped Haar cascades); model fetched from Hugging Face.
    Runs at full resolution so small webcam faces are still recognisable.
    Returns boxes, or the raw YuNet rows (box + landmarks) with rows=True."""
    global _FACE
    if _FACE is None:
        _FACE = cv2.FaceDetectorYN.create(_hf("opencv/face_detection_yunet",
                                              "face_detection_yunet_2023mar.onnx"), "", (320, 320), 0.7, 0.3, 50)
    _FACE.setInputSize((frame.shape[1], frame.shape[0]))
    _, faces = _FACE.detect(frame)
    if faces is None:
        return []
    faces = [f for f in faces if f[2] >= 24]
    return faces if rows else [tuple(float(v) for v in f[:4]) for f in faces]


def face_feature(frame, row):
    """Unit-length SFace identity embedding for one detected face."""
    global _REC
    if _REC is None:
        _REC = cv2.FaceRecognizerSF.create(_hf("opencv/face_recognition_sface",
                                               "face_recognition_sface_2021dec.onnx"), "")
    f = _REC.feature(_REC.alignCrop(frame, row)).ravel()
    return f / (np.linalg.norm(f) + 1e-9)


def streamer_reference(sections, cache=None, per_section=8, same=0.40):
    """Identity embedding of the streamer: the face seen in the most of the
    given moments (guests and on-screen faces come and go; the streamer's cam
    is in nearly all of them).  None when no face is clearly recurrent."""
    if cache and Path(cache).exists():
        return np.load(cache)
    clusters = []  # [feature sum, count, set of section indices]
    for si, sec in enumerate(sections):
        cap = cv2.VideoCapture(str(sec))
        dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(cap.get(cv2.CAP_PROP_FPS), 1)
        for t in np.linspace(1, max(1.5, dur - 1), per_section):
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, fr = cap.read()
            if not ok:
                continue
            for row in detect_faces(fr, rows=True):
                if row[2] < 40:
                    continue
                f = face_feature(fr, row)
                sims = [float(c[0] @ f / np.linalg.norm(c[0])) for c in clusters]
                if sims and max(sims) > same:
                    c = clusters[int(np.argmax(sims))]
                    c[0] += f
                    c[1] += 1
                    c[2].add(si)
                else:
                    clusters.append([f.copy(), 1, {si}])
        cap.release()
    if len(sections) < 2 or not clusters:
        return None
    clusters.sort(key=lambda c: (-len(c[2]), -c[1]))
    top = clusters[0]
    if len(top[2]) < max(2, 0.6 * len(sections)):
        return None
    ref = top[0] / np.linalg.norm(top[0])
    print(f"  streamer face: seen in {len(top[2])}/{len(sections)} moments", flush=True)
    if cache:
        np.save(cache, ref)
    return ref


def plan_framing(src, start, end, W, H, ref=None, match=0.30):
    cap = cv2.VideoCapture(str(src))
    frames, feats = [], []
    for t in np.linspace(start + 0.5, end - 0.5, 24):
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if ok:
            rows = detect_faces(frame, rows=True)
            frames.append([tuple(float(v) for v in r[:4]) for r in rows])
            if ref is not None:
                feats.append([float(face_feature(frame, r) @ ref) if r[2] >= 30 else -1.0 for r in rows])
    cap.release()
    found = []
    if ref is not None:
        # Known streamer identity: follow whichever face is them (multi-cam layouts).
        # Every match counts (the streamer can also appear inside on-screen media,
        # e.g. a fan edit of them); keep the biggest group at one fixed spot,
        # which is their live cam, when it covers most frames.
        hits = [f for fs, ss in zip(frames, feats) for f, s in zip(fs, ss) if s > match]
        tol_m = 0.04 * W
        groups = []
        for f in hits:
            cx = f[0] + f[2] / 2
            for g in groups:
                if abs(g[0] - cx) < tol_m and 0.6 < f[2] / g[1] < 1.6:
                    g[2].append(f)
                    break
            else:
                groups.append([cx, f[2], [f]])
        groups.sort(key=lambda g: -len(g[2]))
        if groups and len(groups[0][2]) >= 8:
            found = groups[0][2]
        elif len(hits) >= 8:
            found = hits
    # Otherwise track the face seen in the most frames at the same spot,
    # not just the largest one: on-screen photos/videos add short-lived faces.
    tol = 0.04 * W
    best, best_n = None, 0
    for cand in ([] if found else (f for fs in frames for f in fs)):
        ccx = cand[0] + cand[2] / 2
        n_hit = sum(any(abs(f[0] + f[2] / 2 - ccx) < tol and 0.6 < f[2] / cand[2] < 1.6 for f in fs)
                    for fs in frames)
        if n_hit > best_n or (n_hit == best_n and best is not None and cand[2] > best[2]):
            best, best_n = cand, n_hit
    if best is not None:
        bcx = best[0] + best[2] / 2
        for fs in frames:
            m = [f for f in fs if abs(f[0] + f[2] / 2 - bcx) < tol and 0.6 < f[2] / best[2] < 1.6]
            if m:
                found.append(min(m, key=lambda f: abs(f[0] + f[2] / 2 - bcx)))
    crop_w = int(H * 9 / 16) // 2 * 2
    if len(found) >= 12:
        f = np.array(found)
        cx, cy = np.median(f[:, 0] + f[:, 2] / 2), np.median(f[:, 1] + f[:, 3] / 2)
        fw = np.median(f[:, 2])
        spread = np.std(f[:, 0] + f[:, 2] / 2) / W
    # A small face that barely moves is a webcam overlay, wherever it sits on screen.
    if len(found) >= 12 and fw < W * 0.12 and spread < 0.03:
        # facecam overlay: box ~ 3.2x face width, 16:9, clamped to frame
        bw = int(min(W * 0.4, fw * 3.2)) // 2 * 2
        bh = int(bw * 9 / 16) // 2 * 2
        bx = int(np.clip(cx - bw / 2, 0, W - bw)) // 2 * 2
        by = int(np.clip(cy - bh / 2, 0, H - bh)) // 2 * 2
        return {"mode": "stack", "cam": (bw, bh, bx, by), "faces": len(found)}
    # Full-frame camera: centre the crop on the largest face per frame (it moves around).
    largest = found if (ref is not None and found) else [max(fs, key=lambda f: f[2] * f[3]) for fs in frames if fs]
    if len(largest) < 4:
        return {"mode": "crop", "x": (W - crop_w) // 2, "crop_w": crop_w, "faces": len(largest)}
    cx = np.median([f[0] + f[2] / 2 for f in largest])
    x = int(np.clip(cx - crop_w / 2, 0, W - crop_w)) // 2 * 2
    return {"mode": "crop", "x": x, "crop_w": crop_w, "faces": len(largest)}


def keep_expr(keep, var="t"):
    return "+".join(f"between({var},{a:.3f},{b:.3f})" for a, b in keep)


FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
ZOOM = 1.18  # punch-in factor


def zoompan(zooms, size, fps, cy=0.5):
    """Hard punch-in during the given output-time windows (centre cy of the height)."""
    if not zooms:
        return ""
    z = f"if({keep_expr(zooms, 'it')},{ZOOM},1)"
    return (f",zoompan=z='{z}':x='iw/2-iw/zoom/2':y='ih*{cy}-ih/zoom*{cy}':d=1:s={size}:fps={fps}")


def video_filter(plan, W, H, ass, keep=None, zooms=None, fps=60, bar_dur=None):
    assf = str(ass).replace("\\", "/").replace(":", r"\:")
    fontsf = str(FONTS_DIR).replace("\\", "/").replace(":", r"\:")
    # Jump cuts happen first, so the captions (already re-timed) line up after them.
    sel = f"select='{keep_expr(keep)}',setpts=N/FRAME_RATE/TB," if keep else ""
    if plan["mode"] == "stack":
        bw, bh, bx, by = plan["cam"]
        gw = int(H * 1080 / 1312) // 2 * 2  # gameplay crop with 1080:1312 aspect
        gx = (W - gw) // 2
        # The webcam box is small in the source, so it gets the strongest upscale:
        # lanczos + a light unsharp keeps the face crisp instead of mushy.
        # Punch-ins zoom the webcam (the reaction), not the gameplay.
        g = (f"[0:v]{sel}split[a][b];[a]crop={bw}:{bh}:{bx}:{by},scale=1080:608:flags=lanczos,"
             f"unsharp=5:5:0.8:5:5:0.0{zoompan(zooms, '1080x608', fps, 0.45)}[cam];"
             f"[b]crop={gw}:{H}:{gx}:0,scale=1080:1312:flags=lanczos,unsharp=5:5:0.4:5:5:0.0[game];"
             f"[cam][game]vstack,setsar=1[base]")
    else:
        g = (f"[0:v]{sel}crop={plan['crop_w']}:{H}:{plan['x']}:0,scale=1080:1920:flags=lanczos,"
             f"unsharp=5:5:0.5:5:5:0.0{zoompan(zooms, '1080x1920', fps, 0.4)},setsar=1[base]")
    if bar_dur:  # progress bar growing along the bottom edge
        g += (f";color=c=0xFFE500:s=1080x14:r={fps}[bar];"
              f"[base][bar]overlay=x='-w+w*t/{bar_dur:.3f}':y=H-h:shortest=1[base2]")
        last = "base2"
    else:
        last = "base"
    return g + f";[{last}]ass='{assf}':fontsdir='{fontsf}'[v]"


def audio_filter(keep=None):
    sel = f"aselect='{keep_expr(keep)}',asetpts=N/SR/TB," if keep else ""
    return f"[0:a]{sel}loudnorm=I=-14:TP=-1:LRA=11[a]"


# ---------------------------------------------------------------- silence cutting
def clip_db(src, s, e):
    """Loudness in dB per 50 ms frame of [s, e]."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{s:.3f}", "-to", f"{e:.3f}", "-i", str(src),
                          "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.float32)
    F = 800
    k = len(a) // F
    return 20 * np.log10(np.sqrt((a[:k * F].reshape(k, F) ** 2).mean(1)) + 1e-9)


def find_zooms(src, s, e, keep, remap, n=3, min_gap=5.0, hold=1.3):
    """Output-time windows for punch-ins on the loudest reactions (shouts, laughs)."""
    db = clip_db(src, s, e)
    if len(db) < 20:
        return []
    sm = np.convolve(db, np.ones(10) / 10, "same")  # 0.5 s smoothing
    thr = np.percentile(sm, 85)
    order = np.argsort(-sm)
    picks = []
    for i in order:
        if sm[i] < thr or len(picks) >= n:
            break
        t = i * 0.05
        if keep and not any(a <= t <= b for a, b in keep):
            continue
        if all(abs(t - q) > min_gap for q in picks):
            picks.append(t)
    zooms = []
    for t in sorted(picks):
        o = remap(t)
        zooms.append((max(0.0, o - 0.25), o + hold))
    return zooms


def find_keep(src, s, e, words, drop_db=12.0, min_sil=0.4, pad=0.15):
    """Clip-local [a, b] spans to keep after removing dead air.

    A pause is cut when it has no transcribed words, lasts >= min_sil and is
    at least drop_db quieter than the clip's median speech level, so loud
    non-speech moments (screams, hype music) stay in.  Returns None when
    nothing worth cutting is found."""
    db = clip_db(src, s, e)
    step = 0.05
    k = len(db)
    if k < 10:
        return None
    speech = np.zeros(k, bool)
    p = int(round(pad / step))
    for w in words:
        i0, i1 = int((w["start"] - s) / step) - p, int((w["end"] - s) / step) + p + 1
        speech[max(0, i0):max(0, min(k, i1))] = True
    level = np.median(db[speech]) if speech.any() else np.percentile(db, 75)
    quiet = (db < level - drop_db) & ~speech
    cuts, i = [], 0
    while i < k:
        if quiet[i]:
            j = i
            while j < k and quiet[j]:
                j += 1
            if (j - i) * step >= min_sil:
                cuts.append((i * step + (pad if i else 0), j * step - (pad if j < k else 0)))
            i = j
        else:
            i += 1
    cuts = [(c0, c1) for c0, c1 in cuts if c1 - c0 >= 0.2]
    if not cuts:
        return None
    keep, t = [], 0.0
    for c0, c1 in cuts:
        if c0 > t:
            keep.append((t, c0))
        t = c1
    if t < k * step:
        keep.append((t, k * step))
    return keep or None


def remap_fn(keep):
    """Map clip-local time to the jump-cut timeline (times inside a cut snap to it)."""
    if not keep:
        return lambda t: t
    starts = np.array([a for a, _ in keep])
    ends = np.array([b for _, b in keep])
    offs = np.concatenate([[0.0], np.cumsum(ends - starts)[:-1]])

    def f(t):
        i = int(np.searchsorted(starts, t, side="right")) - 1
        if i < 0:
            return 0.0
        return float(offs[i] + min(t, ends[i]) - starts[i])
    return f


# ---------------------------------------------------------------- captions
def ass_time(t):
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def ass_escape(s):
    return s.replace("\\", "").replace("{", "(").replace("}", ")")


# Highlight colour for the spoken word, cycling per caption page (ASS is &HBBGGRR&).
PALETTE = {
    "color": ["&H00E5FF&", "&H3CFF3C&", "&HFFE500&", "&HA040FF&", "&H008CFF&"],  # yellow, green, cyan, pink, orange
    "yellow": ["&H00E5FF&"],
}


def write_ass(path, words, clip_start, clip_end, y, remap=None, palette=PALETTE["color"],
              hook=None, hook_y=60, duration=None, viral=True):
    remap = remap or (lambda t: t)
    if viral:
        # Anton, big and heavy, thick outline; hook = black text on a white box.
        cap_style = "Style: Cap,Anton,124,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,0,0,0,0,100,100,1,0,1,9,4,5,40,40,0,1"
        hook_style = (f"Style: Hook,Anton,96,&H00111111,&H00111111,&H00FFFFFF,&H00000000,0,0,0,0,100,100,1,0,"
                      f"3,18,0,8,70,70,{hook_y},1")
    else:
        cap_style = f"Style: Cap,{FONT},88,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,3,5,60,60,0,1"
        hook_style = f"Style: Hook,{FONT},64,&H00111111,&H00111111,&H00FFFFFF,&H00000000,-1,0,0,0,100,100,0,0,3,14,0,8,90,90,{hook_y},1"
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{cap_style}
{hook_style}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ws = [dict(w, start=remap(w["start"] - clip_start), end=remap(w["end"] - clip_start)) for w in words
          if w["end"] > clip_start and w["start"] < clip_end]
    max_chars = 14 if viral else 99  # the big font needs short pages to stay on one line
    pages, cur = [], []
    for w in ws:  # <=3 words per page; break early on long gaps or sentence ends
        n_chars = sum(len(x["word"].strip()) + 1 for x in cur) + len(w["word"].strip())
        if cur and (len(cur) == 3 or n_chars > max_chars or w["start"] - cur[-1]["end"] > 0.6
                    or cur[-1]["word"].strip()[-1:] in ".?!"):
            pages.append(cur)
            cur = []
        cur.append(w)
    if cur:
        pages.append(cur)
    lines = []
    if hook:
        end = duration if duration else (ws[-1]["end"] + 1 if ws else 60)
        pop = r"{\fscx60\fscy60\t(0,180,\fscx100\fscy100)}" if viral else ""
        lines.append(f"Dialogue: 1,{ass_time(0)},{ass_time(end)},Hook,,0,0,0,,{pop}{ass_escape(hook.upper())}")
    for pi, page in enumerate(pages):
        page_end = min(page[-1]["end"] + 0.3, pages[pi + 1][0]["start"] if pi + 1 < len(pages) else 1e9)
        toks = [ass_escape(w["word"].strip().upper()) for w in page]
        col = palette[pi % len(palette)]
        for j, w in enumerate(page):
            s = w["start"]
            e = page[j + 1]["start"] if j + 1 < len(page) else page_end
            if e <= s:
                continue
            # active word pops: starts small and snaps up to 118 % in 90 ms
            pop = r"\fscx75\fscy75\t(0,90,\fscx118\fscy118)" if viral else r"\fscx118\fscy118"
            txt = " ".join((rf"{{\c{col}{pop}}}" + x + r"{\r}") if k == j else x
                           for k, x in enumerate(toks))
            lines.append(f"Dialogue: 0,{ass_time(s)},{ass_time(e)},Cap,,0,0,0,,{{\\pos(540,{y})}}{txt}")
    path.write_text(hdr + "\n".join(lines) + "\n")
    return len(ws)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--chat", help="chat JSON (chat-downloader or TwitchDownloader format)")
    ap.add_argument("-n", type=int, default=3)
    ap.add_argument("--out", default="out")
    ap.add_argument("--model", default="small", help="faster-whisper model for clip captions")
    ap.add_argument("--scan-model", default="base", help="model for full-video scan (no-chat mode)")
    ap.add_argument("--captions", choices=sorted(PALETTE), default="color",
                    help="highlight colour: 'color' cycles yellow/green/cyan/pink/orange per caption")
    ap.add_argument("--moments", choices=["auto", "clips", "chat"], default="auto",
                    help="Twitch: viewer clips first then chat spikes (auto), or only one of them")
    ap.add_argument("--candidates", type=int, default=0,
                    help="Twitch: gather this many candidate moments with transcripts into "
                         "OUT/candidates.json and stop (an editor then writes a --plan)")
    ap.add_argument("--plan", help="Twitch: render an edit plan JSON (picks, trims, hooks, teasers)")
    ap.add_argument("--plain", action="store_true",
                    help="plain style: no hook box, pop animation, punch-ins or progress bar")
    ap.add_argument("--keep-silence", action="store_true", help="don't jump-cut dead air")
    ap.add_argument("--silence-db", type=float, default=12.0,
                    help="cut wordless pauses this many dB below the speech level (default 12)")
    args = ap.parse_args()

    out = Path(args.out)
    work = out / "work"
    work.mkdir(parents=True, exist_ok=True)
    is_url = not Path(args.source).exists()
    vod = twitch_vod_id(args.source) if is_url else None
    info = ytdlp_info(args.source) if is_url and not args.chat else {}
    heatmap = info.get("heatmap") if not vod else None

    # Remote sources with their own moment signal: only download the clip sections.
    if vod:
        dur = float(info["duration"])
        print(f"source: {info.get('title')!r} {dur:.0f}s", flush=True)
        cand_path = out / "candidates.json"
        if args.plan:
            # Render an edit plan: [{"id": candidate id, "start": s, "end": s,
            #   "hook": "TEXT", "teaser": [s, s] | null}], times in VOD seconds.
            cands = {c["id"]: c for c in json.loads(cand_path.read_text())}
            ref = streamer_reference([c["section"] for c in cands.values()], work / f"streamer_ref_{vod}.npy")
            report = []
            for n, item in enumerate(json.loads(Path(args.plan).read_text()), 1):
                c = cands[item["id"]]
                s0 = c["section_start"]
                sec = Path(c["section"])
                a = max(item.get("start", c["s"]), s0) - s0
                b = min(item.get("end", c["e"]), s0 + probe_duration(sec)) - s0
                tz = item.get("teaser")
                r = render_clip(sec, a, b, (a + b) / 2, n, out, work, args, zval=c.get("score", 0),
                                mode=c["mode"], src_offset=s0, hook=item.get("hook"),
                                teaser=(tz[0] - s0, tz[1] - s0) if tz else None,
                                name=item.get("name") or f"clip{n}", ref=ref)
                r.update({k: c[k] for k in ("title", "views", "clippers") if k in c})
                report.append(r)
            (out / "clips.json").write_text(json.dumps(report, indent=2))
            return
        want = args.candidates or args.n
        moments = []
        if args.moments in ("auto", "clips"):
            moments = twitch_clip_moments(vod, dur, want)
            print(f"viewer-clip moments: {len(moments)}", flush=True)
        if len(moments) < want and args.moments in ("auto", "chat"):
            z = robust_z(twitch_chat_profile(vod, dur, work))
            pre, post = 30, 15
            busy = [(m["s"], m["e"]) for m in moments]
            zc = z.copy()
            for a, b in busy:  # don't re-pick a moment viewers already clipped
                zc[max(0, int(a) - 60):int(b) + 60] = -1e9
            for p in pick_peaks(zc, want - len(moments), min_gap=120, dur=dur, pre=pre, post=post):
                q = twitch_refine_peak(vod, p)
                moments.append({"s": max(0, q - pre), "e": min(dur, q + post), "p": q,
                                "score": round(float(z[p]), 2), "mode": "twitch-chat"})
        print("moments:", [(round(m["s"]), round(m["e"]), m["mode"], m.get("title", "")) for m in moments],
              flush=True)
        if args.candidates:
            # Gather candidates with transcripts for an editor (human or LLM) to pick
            # from and write a --plan; nothing is rendered.
            cands = []
            for i, m in enumerate(moments, 1):
                s, e = max(0, m["s"] - 8), min(dur, m["e"] + 8)  # slack for retiming
                sec = download_section(args.source, s, e, work / f"section_{vod}_{int(s)}_{int(e)}.mp4")
                words = transcribe(sec, work, args.model, 0, probe_duration(sec))
                lines, cur, cur_t = [], [], None
                for w in words:
                    if cur and w["seg_start"] != cur_t:
                        lines.append({"t": round(cur[0]["start"] + s, 1), "text": "".join(x["word"] for x in cur).strip()})
                        cur = []
                    cur.append(w)
                    cur_t = w["seg_start"]
                if cur:
                    lines.append({"t": round(cur[0]["start"] + s, 1), "text": "".join(x["word"] for x in cur).strip()})
                cands.append({"id": i, **m, "section": str(sec.resolve()), "section_start": s, "lines": lines})
            cand_path.write_text(json.dumps(cands, indent=2))
            print(f"wrote {cand_path} ({len(cands)} candidates)", flush=True)
            return
        moments.sort(key=lambda m: m["s"])
        secs = [download_section(args.source, m["s"], m["e"],
                                 work / f"section_{vod}_{int(m['s'])}_{int(m['e'])}.mp4") for m in moments]
        ref = streamer_reference(secs, work / f"streamer_ref_{vod}.npy")
        report = []
        for n, (m, sec) in enumerate(zip(moments, secs), 1):
            s = m["s"]
            r = render_clip(sec, 0.0, probe_duration(sec), m["p"] - s, n, out, work, args,
                            zval=m["score"], mode=m["mode"], src_offset=s, hook=m.get("title"), ref=ref)
            r.update({k: m[k] for k in ("title", "views", "clippers") if k in m})
            report.append(r)
        (out / "clips.json").write_text(json.dumps(report, indent=2))
        return

    if heatmap:
        dur = float(info["duration"])
        print(f"source: {info.get('title')!r} {dur:.0f}s", flush=True)
        pre, post = 30, 15
        grid = np.zeros(int(dur) + 1)
        for h in heatmap:
            grid[int(h["start_time"]):int(h["end_time"]) + 1] = h["value"]
        z = (grid - np.median(grid)) / (np.std(grid) + 1e-6)
        mid = [int((h["start_time"] + h["end_time"]) / 2) for h in heatmap]
        zc = np.full_like(grid, -1e9)
        zc[mid] = z[mid]  # only consider segment centres as peaks
        peaks = pick_peaks(zc, args.n, min_gap=120, dur=dur, pre=pre, post=post, thresh=-1e8)
        mode = "most-replayed"
        print(f"mode={mode} peaks={peaks} z={[round(float(z[p]), 1) for p in peaks]}", flush=True)
        report = []
        for n, p in enumerate(peaks, 1):
            s, e = max(0, p - pre), min(dur, p + post)
            sec = download_section(args.source, s, e, work / f"section_{int(s)}_{int(e)}.mp4")
            report.append(render_clip(sec, 0.0, probe_duration(sec), p - s, n, out, work, args,
                                      zval=float(z[p]), mode=mode, src_offset=s))
        (out / "clips.json").write_text(json.dumps(report, indent=2))
        return

    src = fetch(args.source, work)
    dur = probe_duration(src)
    print(f"source: {src} {dur:.0f}s", flush=True)

    if args.chat:
        chat = load_chat(args.chat)
        print(f"chat: {len(chat)} messages", flush=True)
        z = robust_z(chat_scores(chat, dur))
        pre, post = 30, 15
        peaks = pick_peaks(z, args.n, min_gap=60, dur=dur, pre=pre, post=post)
        windows = [(p - pre, p + post, p) for p in peaks]
        mode = "chat"
    else:
        scan = transcribe(src, work, args.scan_model)
        z = robust_z(audio_scores(audio_loudness(src, work), scan, dur), warm=10)
        pre, post = 20, 15
        peaks = pick_peaks(z, args.n, min_gap=45, dur=dur, pre=pre, post=post, thresh=1.0)
        if not peaks:  # very flat audio: just take the top-scoring seconds
            peaks = pick_peaks(z, args.n, min_gap=45, dur=dur, pre=pre, post=post, thresh=-1e9)
        windows = []
        for p in peaks:
            s = snap(scan, p - pre, -1, 6)
            e = snap(scan, p + post, +1, 6)
            windows.append((max(0, s - 0.2), min(dur, e + 0.3), p))
        mode = "audio"
    print(f"mode={mode} peaks={peaks} z={[round(float(z[p]), 1) for p in peaks]}", flush=True)

    report = [render_clip(src, s, e, p, n, out, work, args, zval=float(z[p]), mode=mode)
              for n, (s, e, p) in enumerate(windows, 1)]
    (out / "clips.json").write_text(json.dumps(report, indent=2))


def probe_fps(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=r_frame_rate", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, check=True)
    num, den = r.stdout.strip().split("/")
    return min(60, max(24, round(int(num) / int(den))))


def encode(src, s, e, filt, path):
    sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{s:.3f}", "-to", f"{e:.3f}", "-i", src,
        "-filter_complex", filt,
        # one high-quality encode at the source frame rate (60 fps stays 60);
        # the bitrate cap keeps phone downloads sane without a second lossy pass
        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
        "-maxrate", "12M", "-bufsize", "24M", "-profile:v", "high",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", path])


def render_clip(src, s, e, p, n, out, work, args, zval, mode, src_offset=0.0, hook=None, teaser=None,
                name=None, ref=None):
    """Render [s, e] of src as clip n; p is the peak in src time. Times in the
    report are shifted by src_offset back to the original video's timeline.

    hook: title text pinned at the top.  teaser: (a, b) in src time, a 1-3 s
    payoff played first as a cold open before the clip proper."""
    viral = not args.plain
    W, H = probe_size(src)
    fps = probe_fps(src)
    src_dur = probe_duration(src)
    # short sections: transcribe once in full so re-trimmed plans reuse the cache
    words = transcribe(src, work, args.model, 0, src_dur) if src_dur < 900 else transcribe(src, work, args.model, s, e)
    plan = plan_framing(src, s, e, W, H, ref=ref)
    keep = None if args.keep_silence else find_keep(src, s, e, words, drop_db=args.silence_db)
    remap = remap_fn(keep)
    body_dur = sum(b - a for a, b in keep) if keep else e - s
    zooms = find_zooms(src, s, e, keep, remap) if viral else []
    # stack: hook is a title bar across the cam/gameplay seam, captions in the gameplay
    cap_y = 1300 if plan["mode"] == "crop" else 1240
    hook_y = 170 if plan["mode"] == "crop" else 548
    stem = name or f"clip{n}"
    ass = work / f"{stem}.ass"
    nw = write_ass(ass, words, s, e, y=cap_y, remap=remap, palette=PALETTE[args.captions],
                   hook=hook, hook_y=hook_y, duration=body_dur, viral=viral)
    mp4 = out / f"{stem}.mp4"
    body = work / f"{stem}_body.mp4" if teaser else mp4
    encode(src, s, e, video_filter(plan, W, H, ass, keep, zooms, fps, bar_dur=body_dur if viral else None)
           + ";" + audio_filter(keep), body)
    t_off = 0.0
    if teaser:
        ta, tb = teaser
        t_ass = work / f"{stem}_teaser.ass"
        write_ass(t_ass, words, ta, tb, y=cap_y, palette=PALETTE[args.captions],
                  hook=hook, hook_y=hook_y, duration=tb - ta, viral=viral)
        t_mp4 = work / f"{stem}_teaser.mp4"
        # the cold open is zoomed in the whole way so it reads as a flash-forward
        encode(src, ta, tb, video_filter(plan, W, H, t_ass, None, [(0, tb - ta + 1)], fps) + ";" + audio_filter(),
               t_mp4)
        lst = work / f"{stem}_concat.txt"
        lst.write_text(f"file '{t_mp4.resolve()}'\nfile '{body.resolve()}'\n")
        sh(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
            "-movflags", "+faststart", mp4])
        t_off = tb - ta
    thumb = out / f"{stem}_frame.jpg"
    sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0.5, t_off + remap(p - s)):.2f}", "-i", mp4,
        "-frames:v", "1", thumb])
    text = " ".join(w["word"].strip() for w in words if s <= w["start"] < e)
    final = probe_duration(mp4)
    info = {"clip": mp4.name, "start": round(s + src_offset, 2), "end": round(e + src_offset, 2),
            "peak": round(p + src_offset, 2), "score": round(zval, 2), "mode": mode, "framing": plan["mode"],
            "faces_sampled": plan["faces"], "caption_words": nw, "hook": hook,
            "teaser": [round(t + src_offset, 2) for t in teaser] if teaser else None,
            "zooms": len(zooms), "silence_cut_s": round((e - s) - body_dur, 1),
            "duration": round(final, 1), "transcript": text}
    print(json.dumps({k: v for k, v in info.items() if k != "transcript"}), flush=True)
    return info


if __name__ == "__main__":
    sys.exit(main())
