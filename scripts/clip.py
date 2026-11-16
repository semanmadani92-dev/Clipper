"""Clip a long video into 9:16 vertical shorts with word-by-word captions.

Usage:
    python scripts/clip.py SOURCE [--chat CHAT.json] [-n 3] [--out out/]

SOURCE is a local video file or a URL (yt-dlp).

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

Captions: faster-whisper word timestamps -> ASS, 3-word pages, active word
highlighted yellow and scaled up, burned in with libass.
"""
import argparse, json, os, re, subprocess, sys, time, urllib.request
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
def transcribe(src, work, model_size, start=0.0, end=None):
    """Word list [{start,end,word}] in source time.  Cached per range."""
    key = f"{Path(src).stem}_{model_size}_{start:.0f}_{end if end is None else round(end)}"
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


def detect_faces(frame):
    """YuNet face detector (OpenCV 5 dropped Haar cascades); model fetched from Hugging Face."""
    global _FACE
    if _FACE is None:
        from huggingface_hub import hf_hub_download
        model = hf_hub_download("opencv/face_detection_yunet", "face_detection_yunet_2023mar.onnx")
        _FACE = cv2.FaceDetectorYN.create(model, "", (320, 320), 0.7, 0.3, 50)
    scale = 640 / frame.shape[1]
    small = cv2.resize(frame, None, fx=scale, fy=scale)
    _FACE.setInputSize((small.shape[1], small.shape[0]))
    _, faces = _FACE.detect(small)
    if faces is None:
        return []
    return [(x / scale, y / scale, w / scale, h / scale) for x, y, w, h in faces[:, :4]]


def plan_framing(src, start, end, W, H):
    cap = cv2.VideoCapture(str(src))
    frames = []
    for t in np.linspace(start + 0.5, end - 0.5, 24):
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if ok:
            frames.append(detect_faces(frame))
    cap.release()
    # Track the face seen in the most frames at the same spot (the streamer),
    # not just the largest one: on-screen photos/videos add short-lived faces.
    tol = 0.04 * W
    best, best_n = None, 0
    for cand in (f for fs in frames for f in fs):
        ccx = cand[0] + cand[2] / 2
        n_hit = sum(any(abs(f[0] + f[2] / 2 - ccx) < tol and 0.6 < f[2] / cand[2] < 1.6 for f in fs)
                    for fs in frames)
        if n_hit > best_n or (n_hit == best_n and best is not None and cand[2] > best[2]):
            best, best_n = cand, n_hit
    found = []
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
    largest = [max(fs, key=lambda f: f[2] * f[3]) for fs in frames if fs]
    if len(largest) < 4:
        return {"mode": "crop", "x": (W - crop_w) // 2, "crop_w": crop_w, "faces": len(largest)}
    cx = np.median([f[0] + f[2] / 2 for f in largest])
    x = int(np.clip(cx - crop_w / 2, 0, W - crop_w)) // 2 * 2
    return {"mode": "crop", "x": x, "crop_w": crop_w, "faces": len(largest)}


def video_filter(plan, W, H, ass):
    assf = str(ass).replace("\\", "/").replace(":", r"\:")
    if plan["mode"] == "stack":
        bw, bh, bx, by = plan["cam"]
        gw = int(H * 1080 / 1312) // 2 * 2  # gameplay crop with 1080:1312 aspect
        gx = (W - gw) // 2
        return (f"[0:v]split[a][b];[a]crop={bw}:{bh}:{bx}:{by},scale=1080:608[cam];"
                f"[b]crop={gw}:{H}:{gx}:0,scale=1080:1312[game];"
                f"[cam][game]vstack,setsar=1,ass='{assf}'[v]")
    return (f"[0:v]crop={plan['crop_w']}:{H}:{plan['x']}:0,scale=1080:1920,setsar=1,"
            f"ass='{assf}'[v]")


# ---------------------------------------------------------------- captions
def ass_time(t):
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def ass_escape(s):
    return s.replace("\\", "").replace("{", "(").replace("}", ")")


def write_ass(path, words, clip_start, clip_end, y):
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{FONT},88,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,3,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ws = [dict(w, start=w["start"] - clip_start, end=w["end"] - clip_start) for w in words
          if w["end"] > clip_start and w["start"] < clip_end]
    pages, cur = [], []
    for w in ws:  # 3 words per page; break early on long gaps or sentence ends
        if cur and (len(cur) == 3 or w["start"] - cur[-1]["end"] > 0.6
                    or cur[-1]["word"].strip()[-1:] in ".?!"):
            pages.append(cur)
            cur = []
        cur.append(w)
    if cur:
        pages.append(cur)
    lines = []
    for pi, page in enumerate(pages):
        page_end = min(page[-1]["end"] + 0.3, pages[pi + 1][0]["start"] if pi + 1 < len(pages) else 1e9)
        toks = [ass_escape(w["word"].strip().upper()) for w in page]
        for j, w in enumerate(page):
            s = w["start"]
            e = page[j + 1]["start"] if j + 1 < len(page) else page_end
            if e <= s:
                continue
            txt = " ".join((r"{\c&H00E5FF&\fscx118\fscy118}" + x + r"{\r}") if k == j else x
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
    args = ap.parse_args()

    out = Path(args.out)
    work = out / "work"
    work.mkdir(parents=True, exist_ok=True)
    is_url = not Path(args.source).exists()
    vod = twitch_vod_id(args.source) if is_url else None
    info = ytdlp_info(args.source) if is_url and not args.chat else {}
    heatmap = info.get("heatmap") if not vod else None

    # Remote sources with their own moment signal: only download the clip sections.
    if vod or heatmap:
        dur = float(info["duration"])
        print(f"source: {info.get('title')!r} {dur:.0f}s", flush=True)
        pre, post = 30, 15
        if vod:
            z = robust_z(twitch_chat_profile(vod, dur, work))
            rough = pick_peaks(z, args.n, min_gap=120, dur=dur, pre=pre, post=post)
            refined = {}
            for p in rough:
                q = twitch_refine_peak(vod, p)
                refined[q] = float(z[p])  # report the spike's sampled score
            peaks = sorted(refined)
            z = z.copy()
            for q, zv in refined.items():
                z[q] = zv
            mode = "twitch-chat"
        else:
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
            sec = download_section(args.source, s, e, work / f"section{n}.mp4")
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


def render_clip(src, s, e, p, n, out, work, args, zval, mode, src_offset=0.0):
    """Render [s, e] of src as clip n; p is the peak in src time. Times in the
    report are shifted by src_offset back to the original video's timeline."""
    W, H = probe_size(src)
    words = transcribe(src, work, args.model, s, e)
    plan = plan_framing(src, s, e, W, H)
    ass = work / f"clip{n}.ass"
    nw = write_ass(ass, words, s, e, y=1460 if plan["mode"] == "crop" else 1180)
    mp4 = out / f"clip{n}_vertical.mp4"
    sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{s:.2f}", "-to", f"{e:.2f}", "-i", src,
        "-filter_complex", video_filter(plan, W, H, ass) + ";[0:a]loudnorm=I=-14:TP=-1:LRA=11[a]",
        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
        "-movflags", "+faststart", mp4])
    thumb = out / f"clip{n}_frame.jpg"
    sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0.5, p - s):.2f}", "-i", mp4, "-frames:v", "1", thumb])
    text = " ".join(w["word"].strip() for w in words if s <= w["start"] < e)
    info = {"clip": mp4.name, "start": round(s + src_offset, 2), "end": round(e + src_offset, 2),
            "peak": round(p + src_offset, 2), "z": round(zval, 2), "mode": mode, "framing": plan["mode"],
            "faces_sampled": plan["faces"], "caption_words": nw, "transcript": text}
    print(json.dumps({k: v for k, v in info.items() if k != "transcript"}), flush=True)
    return info


if __name__ == "__main__":
    sys.exit(main())
