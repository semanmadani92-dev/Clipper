"""Offline smoke test of the Clipper pipeline stages that don't need network.

1. Make a synthetic 1920x1080 "stream" (gameplay + facecam box + tone).
2. Make a synthetic chat log in TwitchDownloader JSON shape with two spikes.
3. Detect spikes: unique chatters / 10 s, rolling median+MAD robust z, peak pick.
4. For each spike cut [peak-30s, peak+10s] -> 9:16 facecam-over-gameplay split,
   burn word-by-word karaoke ASS captions, loudness-normalize.
"""
import json, random, subprocess, sys
from pathlib import Path
import numpy as np

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "out")
OUT.mkdir(parents=True, exist_ok=True)
DUR = 180
FONT = "DejaVu Sans"


def sh(cmd):
    print("+", " ".join(cmd)[:160])
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


# 1. synthetic stream: testsrc2 gameplay, smptebars "facecam" bottom-left, running clock
src = OUT / "stream.mp4"
if not src.exists():
    sh(["ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc2=size=1920x1080:rate=30:duration={DUR}",
        "-f", "lavfi", "-i", f"smptebars=size=480x270:rate=30:duration={DUR}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={DUR}",
        "-filter_complex",
        "[0][1]overlay=40:H-310[v];"
        f"[v]drawtext=font='{FONT}':text='STREAM %{{pts\\:hms}}':x=760:y=40:fontsize=64:fontcolor=white:box=1:boxcolor=black@0.6[vo]",
        "-map", "[vo]", "-map", "2", "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-shortest", str(src)])

# 2. synthetic chat (TwitchDownloader-like): baseline ~0.8 msg/s, spikes at 70 s and 150 s
random.seed(1)
comments = []
for t in np.arange(0, DUR, 0.1):
    rate = 0.08
    for spike in (70, 150):
        if spike - 4 <= t <= spike + 6:
            rate = 1.2
    if random.random() < rate:
        hype = rate > 0.5
        comments.append({
            "content_offset_seconds": round(float(t), 2),
            "commenter": {"name": f"user{random.randint(1, 400 if hype else 60)}"},
            "message": {"body": random.choice(["KEKW", "LUL", "OMEGALUL", "Pog", "CLIP IT"]) if hype
                        else random.choice(["hi", "gg", "nice", "lol", "what game is this"])},
        })
(OUT / "chat.json").write_text(json.dumps({"comments": comments}))

# 3. detector
REACT = {"KEKW": 2.0, "LUL": 1.5, "OMEGALUL": 2.0, "Pog": 1.5, "CLIP IT": 3.0}
users_per_sec = [set() for _ in range(DUR)]
react = np.zeros(DUR)
for c in comments:
    s = int(c["content_offset_seconds"])
    users_per_sec[s].add(c["commenter"]["name"])
    react[s] += REACT.get(c["message"]["body"], 0)
W = 10
uniq = np.array([len(set().union(*users_per_sec[max(0, i - W + 1):i + 1])) for i in range(DUR)], float)
score = uniq + 0.3 * np.convolve(react, np.ones(W), "full")[:DUR]
z = np.zeros(DUR)
for i in range(DUR):
    base = score[max(0, i - 300):max(1, i - W)]  # trailing baseline, excludes current window
    med = np.median(base)
    mad = max(np.median(np.abs(base - med)) * 1.4826, 1.0)
    z[i] = (score[i] - med) / mad
peaks = []
for i in range(30, DUR):  # 30 s warmup
    if z[i] >= 3 and z[i] == z[max(0, i - 15):i + 16].max():
        if not peaks or i - peaks[-1] > 30:
            peaks.append(i)
print("spike peaks (s):", peaks, "z:", [round(z[p], 1) for p in peaks])

# 4. render clips
WORDS = "OH NO HE DID NOT JUST DO THAT CHAT CLIP IT RIGHT NOW".split()


def ass_time(t):
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def write_ass(path, start_in_clip):
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{FONT},96,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,8,0,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines, t = [], start_in_clip
    for i in range(0, len(WORDS), 3):  # 3-word pages, active word yellow + pop
        page = WORDS[i:i + 3]
        for j, w in enumerate(page):
            txt = " ".join(
                (r"{\c&H00FFFF&\fscx115\fscy115}" + x + r"{\r}") if k == j else x for k, x in enumerate(page))
            lines.append(f"Dialogue: 0,{ass_time(t)},{ass_time(t + 0.4)},Cap,,0,0,0,,{{\\pos(540,1100)}}{txt}")
            t += 0.4
    path.write_text(hdr + "\n".join(lines) + "\n")


for n, p in enumerate(peaks, 1):
    start, end = max(0, p - 30), min(DUR, p + 10)
    ass = OUT / f"clip{n}.ass"
    write_ass(ass, start_in_clip=p - 4 - start)  # captions over the moment itself
    out = OUT / f"clip{n}_vertical.mp4"
    sh(["ffmpeg", "-y", "-ss", str(start), "-to", str(end), "-i", str(src),
        "-filter_complex",
        "[0:v]split[a][b];"
        "[a]crop=480:270:40:770,scale=1080:608[cam];"       # facecam region
        "[b]crop=1080:1080:420:0,scale=1312:1312,crop=1080:1312[game];"  # center of gameplay
        f"[cam][game]vstack,setsar=1,ass={ass}[v];"
        "[0:a]loudnorm=I=-14:TP=-1:LRA=11[a1]",
        "-map", "[v]", "-map", "[a1]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", str(out)])
    sh(["ffmpeg", "-y", "-ss", str(p - 4 - start + 1.0), "-i", str(out), "-frames:v", "1", str(OUT / f"clip{n}_frame.png")])
    print(f"clip{n}: {start}s-{end}s (peak {p}s) -> {out}")
