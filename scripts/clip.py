"""Clip a long video into 9:16 vertical shorts with word-by-word captions.

Usage:
    python scripts/clip.py SOURCE [--chat CHAT.json] [-n 3] [--out out/]

SOURCE is a local video file or a URL (downloaded with yt-dlp).

Moment selection:
  * Twitch VOD URL, or --chat given: chat spikes (unique chatters per 10 s plus
    emote reactions, robust z-score against a trailing 5 min baseline).  Each
    clip starts 30 s before the spike peak and ends 15 s after it.
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
import argparse, json, re, subprocess, sys
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
def is_twitch_vod(src):
    return bool(re.search(r"twitch\.tv/(videos/\d+|\w+/v/\d+)", src))


def fetch(src, work):
    if Path(src).exists():
        return Path(src)
    out = work / "source.%(ext)s"
    sh(["yt-dlp", "--no-playlist", "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
        "--merge-output-format", "mp4", "-o", out, src])
    return next(work.glob("source.*"))


def fetch_twitch_chat(src, work):
    path = work / "chat.json"
    if not path.exists():
        sh(["chat_downloader", src, "--output", path, "--quiet"])
    return path


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
            react[s] += sum(REACT.get(tok, 0) for tok in text.split())
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
    key = f"{model_size}_{start:.0f}_{end if end is None else round(end)}"
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
    found = []
    for t in np.linspace(start + 0.5, end - 0.5, 24):
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        faces = detect_faces(frame)
        if faces:
            found.append(max(faces, key=lambda f: f[2] * f[3]))  # largest face
    cap.release()
    crop_w = int(H * 9 / 16) // 2 * 2
    if len(found) < 4:
        return {"mode": "crop", "x": (W - crop_w) // 2, "crop_w": crop_w, "faces": len(found)}
    f = np.array(found)
    cx, cy = np.median(f[:, 0] + f[:, 2] / 2), np.median(f[:, 1] + f[:, 3] / 2)
    fw = np.median(f[:, 2])
    spread = np.std(f[:, 0] + f[:, 2] / 2) / W
    corner = (cx < W * 0.3 or cx > W * 0.7) and (cy < H * 0.35 or cy > H * 0.65)
    if fw < W * 0.12 and spread < 0.02 and corner and len(found) >= 12:
        # facecam overlay: box ~ 3.2x face width, 16:9, clamped to frame
        bw = int(min(W * 0.4, fw * 3.2)) // 2 * 2
        bh = int(bw * 9 / 16) // 2 * 2
        bx = int(np.clip(cx - bw / 2, 0, W - bw)) // 2 * 2
        by = int(np.clip(cy - bh / 2, 0, H - bh)) // 2 * 2
        return {"mode": "stack", "cam": (bw, bh, bx, by), "faces": len(found)}
    x = int(np.clip(cx - crop_w / 2, 0, W - crop_w)) // 2 * 2
    return {"mode": "crop", "x": x, "crop_w": crop_w, "faces": len(found)}


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
    src = fetch(args.source, work)
    dur = probe_duration(src)
    W, H = probe_size(src)
    print(f"source: {src} {W}x{H} {dur:.0f}s", flush=True)

    chat_path = args.chat or (fetch_twitch_chat(args.source, work) if is_twitch_vod(args.source) else None)
    if chat_path:
        chat = load_chat(chat_path)
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

    report = []
    for n, (s, e, p) in enumerate(windows, 1):
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
        info = {"clip": mp4.name, "start": round(s, 2), "end": round(e, 2), "peak": p,
                "z": round(float(z[p]), 2), "mode": mode, "framing": plan["mode"],
                "faces_sampled": plan["faces"], "caption_words": nw, "transcript": text}
        report.append(info)
        print(json.dumps({k: v for k, v in info.items() if k != "transcript"}), flush=True)
    (out / "clips.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    sys.exit(main())
