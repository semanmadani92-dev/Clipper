# Open-source / self-hostable "link -> viral clip" pipeline (state as of Nov 2026)

Method note: GitHub star counts, last-push dates, archive flags and licenses below come from the GitHub REST search API queried on 2026-11-16 (the `repos/` endpoint was blocked in this session, but `search/repositories?q=repo:owner/name` worked). READMEs were pulled from raw.githubusercontent.com on the same date. platform.openai.com, developers.openai.com and remotion.dev could not be fetched from this sandbox, so OpenAI facts come from search-result excerpts and Remotion facts come from the docs source in the Remotion GitHub repo. Commands marked "illustrative" are standard usage I wrote for the report writer. They are not quoted from a source, so test them before relying on them.

## 1. Downloading (yt-dlp, streamlink, partial VOD downloads, YouTube PO token / SABR)

### Takeaway
yt-dlp is still the default downloader (about 208k stars, pushed 2026-11-15). For clipping, `--download-sections "*start-end"` fetches only a time range from YouTube, Twitch VODs and Kick VODs. Since late 2025, full YouTube support needs the `yt-dlp-ejs` component plus a JavaScript runtime (Deno is the default). YouTube's PO-token requirements and SABR-only formats mean a production pipeline should run a PO-token provider plugin (bgutil) and expect occasional breakage. A self-hosted service has to keep yt-dlp updated.

### Cited Findings
- yt-dlp: 208,337 stars, last push 2026-11-15, Unlicense — [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp)
- The README says `ffmpeg`, `ffprobe`, `yt-dlp-ejs` and a supported JS runtime are "highly recommended". yt-dlp-ejs is "Required for full YouTube support", and "A JavaScript runtime/engine like deno (recommended), node.js, bun, or QuickJS is also required to run yt-dlp-ejs" — [yt-dlp README](https://github.com/yt-dlp/yt-dlp)
- `--js-runtimes RUNTIME[:PATH]`: supported runtimes in priority order are deno, node, quickjs, bun, and "Only 'deno' is enabled by default". `--remote-components ejs:npm|ejs:github` lets yt-dlp fetch the EJS scripts if the package isn't installed. By default no remote components are allowed — [yt-dlp README](https://github.com/yt-dlp/yt-dlp)
- A companion repo, yt-dlp/ejs ("External JavaScript for yt-dlp supporting many runtimes"), has 486 stars and was pushed 2026-10-26 — [yt-dlp/ejs](https://github.com/yt-dlp/ejs)
- `--download-sections REGEX`: "Download only chapters that match the regular expression. A '*' prefix denotes time-range instead of chapter. Negative timestamps are calculated from the end." The option can be repeated, e.g. `--download-sections "*10:15-inf" --download-sections "intro"` — [yt-dlp README](https://github.com/yt-dlp/yt-dlp)
- `--force-keyframes-at-cuts`: "Force keyframes at cuts when downloading/splitting/removing sections. This is slow due to needing a re-encode, but the resulting video may have fewer artifacts". The default is off — [yt-dlp README](https://github.com/yt-dlp/yt-dlp)
- Twitch VOD partial download example: `yt-dlp "https://www.twitch.tv/videos/2385736857" --download-sections "*02:34:30-02:34:50"`. Seconds also work (`*21-87`). Section downloads require ffmpeg — [VideoHelp forum](https://forum.videohelp.com/showthread.php?p=2768027); [gigazine walkthrough](https://gigazine.net/gsc_news/en/20220624-yt-dlp-download-sections)
- twitch-dlp (npm) is an alternative that takes the same syntax and can also download live/sub-only VODs: `npx twitch-dlp https://www.twitch.tv/videos/2022789761 --download-sections "*15:00-25:00"` — [twitch-dlp README](https://cdn.jsdelivr.net/npm/twitch-dlp@0.6.3/README.md)
- Kick: the yt-dlp source has `KickIE` (live channel), `KickVODIE` (`kick.com/<user>/videos/<uuid>`), `KickClipIE`, `KickVideosIE` and `KickClipsIE` extractors — [yt-dlp kick.py](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/kick.py)
- PO Token Guide (last edited Jul 12, 2026). GVS PO token required for `web_safari`, `mweb`, `tv_simply`, `web_music`, `web_creator` and `web` (`web` also needs one for subs). `android`/`ios` need GVS or Player tokens. `tv`, `web_embedded` and `android_vr` don't need one. For `web` it says "Only SABR formats available". For `tv`: "Only SABR formats available in some cases" and "All formats DRM'd if cookies (logged-in or active guest) aren't passed". Recommendation: "Use a PO Token Provider plugin to provide the mweb client". "Manually extracting PO Tokens is no longer recommended" because tokens are now bound to the video ID — [yt-dlp wiki: PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide)
- In 2026 users still saw "Some web client https formats have been skipped as they are missing a URL. YouTube is forcing SABR streaming for this client" (tracking issue #12482). The third-party plugin yt-dlp-ytse adds experimental SABR/UMP downloads (`--extractor-args youtube:formats=sabr`) but warns against relying on it — [yt-dlp issue #15897](https://github.com/yt-dlp/yt-dlp/issues/15897); [yt-dlp-ytse](https://github.imc.re/coletdjnz/yt-dlp-ytse)
- bgutil-ytdlp-pot-provider (905 stars, pushed 2026-10-07, GPL-3.0) generates PO tokens using LuanRT's BgUtils. It runs as an HTTP server on port 4416 (`docker run --name bgutil-provider -d --init -p 127.0.0.1:4416:4416 brainicism/bgutil-ytdlp-pot-provider`) or as a script, needs yt-dlp >= 2025.05.22 and Node >= 22 or Deno >= 2. Caution: "Providing a PO token does not guarantee bypassing 403 errors or bot checks" — [Brainicism/bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider)
- streamlink is still active (11,931 stars, pushed 2026-11-14, BSD-2) — [streamlink/streamlink](https://github.com/streamlink/streamlink)
- TwitchDownloader (4,054 stars, pushed 2026-11-15, MIT) handles Twitch VOD/clip download plus chat download/render/replay, which is relevant for chat-spike highlight detection — [lay295/TwitchDownloader](https://github.com/lay295/TwitchDownloader)

### Inferences
- Illustrative download command for one candidate window from a Twitch/Kick/YouTube URL:
  `yt-dlp -f "bv*[height<=1080]+ba/b[height<=1080]" --download-sections "*01:23:10-01:24:40" --force-keyframes-at-cuts -o "%(id)s_%(section_start)s.%(ext)s" URL`.
  Dropping `--force-keyframes-at-cuts` is much faster but cuts land on keyframes, so the clip may start a second or two early. Since the clip is re-encoded later anyway, a common pattern is to download with a few seconds of padding and do the frame-accurate trim in the final ffmpeg render.
- A two-stage pipeline works well for long VODs: (1) fetch audio only (`-f ba`), plus chat replay for Twitch, to transcribe and score; (2) use `--download-sections` to fetch video only for the chosen windows. This avoids downloading multi-hour VODs.
- YouTube is the fragile source. Budget for keeping yt-dlp nightly/updated, running Deno, the bgutil provider container, and possibly cookies from a throwaway account. Datacenter IPs are the most likely to be flagged ("Sign in to confirm you're not a bot").

### Gaps
- I couldn't fetch the current yt-dlp EJS wiki page or the 2026 changelog, so I couldn't confirm the exact release where a JS runtime became mandatory, or whether SABR downloading has landed natively in yt-dlp by Nov 2026.
- I didn't verify whether `--download-sections` on Twitch HLS fetches only the needed segments or the whole playlist. The forum reports imply it is efficient, but there's no official statement.

## 2. Transcription with word-level timestamps

### Takeaway
For self-hosting, faster-whisper (CTranslate2) with `word_timestamps=True` and batched inference is the practical default; Clips Kitty and OpenShorts both use it. WhisperX adds wav2vec2 forced alignment for tighter word boundaries plus pyannote diarization. whisper.cpp is the CPU/Apple/edge choice and is what Remotion's TikTok template uses. NVIDIA Parakeet TDT 0.6B v3 is far faster with word timestamps but covers fewer languages. Among hosted APIs, OpenAI's word timestamps exist only on `whisper-1`, which is deprecated with shutdown on Feb 26, 2027. Deepgram and AssemblyAI return word timestamps at roughly $0.15–$0.46/hour.

### Cited Findings
- faster-whisper: 26,797 stars, pushed 2026-11-12, MIT — [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- faster-whisper benchmark (13 min of audio, large-v2 on an RTX 3070 Ti 8GB): openai/whisper fp16 2m23s / 4.7GB; whisper.cpp (flash attention) 1m05s; faster-whisper fp16 1m03s / 4.5GB; faster-whisper `batch_size=8` fp16 **17s** / 6.1GB; int8 batched 16s / 4.5GB — [faster-whisper README](https://github.com/SYSTRAN/faster-whisper)
- faster-whisper on CPU (small model, i7-12700K, 8 threads): openai/whisper 6m58s; whisper.cpp 2m05s; whisper.cpp+OpenVINO 1m45s; faster-whisper int8 1m42s; faster-whisper batched int8 51s — [faster-whisper README](https://github.com/SYSTRAN/faster-whisper)
- Batched API: `BatchedInferencePipeline(model=WhisperModel("turbo", device="cuda", compute_type="float16")).transcribe("audio.mp3", batch_size=16)`. Word-level timestamps are supported, Silero VAD is integrated (`vad_filter=True`, on by default for batched mode), and distil-large-v3 is compatible — [faster-whisper README](https://github.com/SYSTRAN/faster-whisper)
- WhisperX: 25,376 stars, pushed 2026-11-12, BSD-2-Clause. Claims "70x realtime with large-v2" batched inference, <8GB GPU for large-v2, "Accurate word-level timestamps using wav2vec2 alignment", diarization via pyannote `speaker-diarization-community-1` (needs an HF token and accepted license), and VAD preprocessing to reduce hallucination. A 2026 addition, "Context-Aware Batching", enables condition_on_previous_context within batched transcription. Installing Numba speeds alignment "30×–100×". Its own limitations section says "Diarization is far from perfect" — [m-bain/whisperX](https://github.com/m-bain/whisperX)
- WhisperX notes that vanilla Whisper's timestamps "are at the utterance-level, not per word, and can be inaccurate by several seconds" — [WhisperX README](https://github.com/m-bain/whisperX)
- WhisperX CLI examples: `whisperx audio.wav --model large-v2 --diarize --highlight_words True`; CPU: `whisperx audio.wav --compute_type int8 --device cpu` — [WhisperX README](https://github.com/m-bain/whisperX)
- whisper.cpp: 55,247 stars, pushed 2026-11-16, MIT — [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp)
- openai/whisper: 112,808 stars, last push 2026-08-31 — [openai/whisper](https://github.com/openai/whisper)
- Distil-Whisper: 4,118 stars, **last push 2025-01-08**, so effectively dormant ("6x faster, 50% smaller, within 1% WER") — [huggingface/distil-whisper](https://github.com/huggingface/distil-whisper)
- stable-ts (Whisper timestamp stabilization / forced alignment) is **archived** (last push 2026-05-30). whisper-timestamped is still active (2,861 stars, pushed 2026-09-28, AGPL-3.0) — [jianfch/stable-ts](https://github.com/jianfch/stable-ts); [linto-ai/whisper-timestamped](https://github.com/linto-ai/whisper-timestamped)
- Parakeet TDT 0.6B v3 emits char/word/segment timestamps through the NeMo API. NVIDIA reports RTFx 2940 at batch 128 and about 6.34% average WER on the HF Open ASR leaderboard. A third-party blog claims RTFx about 3,332, which conflicts with NVIDIA's figure — [NVIDIA NGC Parakeet collection](https://catalog.ngc.nvidia.com/orgs/nvidia/-/collections/parakeet-tdt-0.6b/-); [build.nvidia.com model card](https://build.nvidia.com/nvidia/parakeet-tdt-0_6b/modelcard); [localaimaster blog](https://localaimaster.com/blog/parakeet-vs-whisper)
- Parakeet runtimes: achetronic/parakeet is an OpenAI-Whisper-compatible ASR server on Parakeet TDT 0.6B via ONNX for CPU/GPU (377 stars, pushed 2026-11-09). parakeet-mlx targets Apple Silicon (997 stars, pushed 2026-11-05). CrispASR is a C++ ggml hub covering Parakeet TDT, Canary 1B and Voxtral (814 stars, pushed 2026-11-16) — [achetronic/parakeet](https://github.com/achetronic/parakeet); [senstella/parakeet-mlx](https://github.com/senstella/parakeet-mlx); [CrispStrobe/CrispASR](https://github.com/CrispStrobe/CrispASR)
- NeMo's main repo appears to have moved: the GitHub search API lists NVIDIA-NeMo/Speech (18,760 stars, pushed 2026-11-16) with NeMo's description ("A scalable generative AI framework…"), and `NVIDIA/NeMo` didn't resolve via search — [NVIDIA-NeMo/Speech](https://github.com/NVIDIA-NeMo/Speech)
- OpenAI: "The timestamp_granularities[] parameter is only supported for whisper-1". The gpt-4o-transcribe / gpt-4o-mini-transcribe models support only `json` output, not `verbose_json`. Search excerpts of the current guide say whisper-1, gpt-4o-transcribe, gpt-4o-mini-transcribe and gpt-4o-transcribe-diarize are deprecated with shutdown Feb 26, 2027, that new work should start with `gpt-transcribe`, and that "Existing integrations can use the deprecated whisper-1 model for word or segment timestamps until February 26, 2027." These come from search-result excerpts because the page wasn't fetchable here — [OpenAI speech-to-text guide](https://developers.openai.com/api/docs/guides/speech-to-text)
- Hosted pricing (secondary sources, which conflict): Deepgram Nova-3 monolingual about $0.46/hr pay-as-you-go ($0.0077/min) and $0.39/hr on Growth. AssemblyAI Universal-2 about $0.15/hr and Universal-3.5 Pro about $0.21/hr. A vendor comparison puts base + speaker ID at AssemblyAI $0.17/hr vs Deepgram $0.58/hr — [AssemblyAI pricing blog](https://assemblyai.com/blog/speech-to-text-api-pricing); [happyrobot Deepgram pricing](https://www.happyrobot.ai/hub/deepgram-pricing); [costbench](https://costbench.com/compare/assemblyai-vs-deepgram/)
- Real-world cost datapoint: Clips Kitty reports that a 2-hour video cost about $0.11 on OpenRouter with Whisper large-v3-turbo transcribing and Gemma 4 26B-A4B picking clips — [ColinGPT9/clips-studio](https://github.com/ColinGPT9/clips-studio)
- FunClip uses Alibaba Paraformer-Large (Chinese) with integrated timestamps, SeACo-Paraformer hotwords, CAM++ speaker ID, a SenseVoice option (multilingual + emotion + audio-event detection) and, since v2.2.0 (2026-08-30), a MOSS-Transcribe-Diarize path — [modelscope/FunClip](https://github.com/modelscope/FunClip)

### Inferences
- Illustrative faster-whisper call for caption-grade word timing:
  ```python
  from faster_whisper import WhisperModel, BatchedInferencePipeline
  m = BatchedInferencePipeline(model=WhisperModel("large-v3-turbo", device="cuda", compute_type="float16"))
  segs, info = m.transcribe("audio.wav", batch_size=16, word_timestamps=True, vad_filter=True)
  words = [(w.start, w.end, w.word) for s in segs for w in s.words]
  ```
- Scaling from the benchmark (13 min in 17s batched on an 8GB consumer GPU, about 45x realtime), a 3-hour VOD should transcribe in roughly 4–5 minutes on a mid-range GPU with large-v2/turbo. On CPU, use small/medium int8 or whisper.cpp, and expect about realtime or slower for large models.
- For captions, the decision is roughly: faster-whisper word timestamps (good enough, simplest) → WhisperX alignment (tighter boundaries, diarization for speaker-aware cropping) → Parakeet (English/EU languages at very high throughput). Avoid building on OpenAI `whisper-1` word timestamps given the Feb 2027 shutdown.

### Gaps
- I couldn't verify whether OpenAI's new `gpt-transcribe` returns word timestamps, or its price.
- No authoritative, dated, apples-to-apples GPU cost per hour for WhisperX vs Parakeet; the leaderboard RTFx figures conflict.
- Deepgram's and AssemblyAI's official pricing pages weren't fetched. Figures are from vendor blogs and aggregators and may be stale.

## 3. Highlight selection

### Takeaway
Almost every open-source clipper uses the same core: a timestamped transcript sent to an LLM that returns N segments with scores, hooks and reasons. Older versions used GPT-4o-mini and now mostly Gemini Flash, Claude, DeepSeek or local Ollama models. The better 2026 tools fuse non-text signals (audio loudness/laughter bursts, scene cuts, motion, face-area change, Twitch chat replay activity, YouTube "most replayed" heatmap) into the LLM prompt and rerank finalists head-to-head. Several projects warn that small local models (3B–7B) are poor at absolute scoring and timestamp math.

### Cited Findings
- AI-Youtube-Shorts-Generator ranks highlights by "hooks, emotional peaks, opinion bombs, revelation moments, conflict, quotable lines, story peaks, and practical value". Each clip gets "a viral score, an opening hook line, and a one-sentence explanation". Videos over 30 min are chunked with overlap, and overlapping highlights are deduped by score. Local-mode defaults are `gpt-4o-mini` or `gemini-2.5-flash` — [Anil-matcha/AI-Youtube-Shorts-Generator](https://github.com/Anil-matcha/AI-Youtube-Shorts-Generator)
- Clips Kitty scoring: "The transcript is one signal among five. Audio gives loudness spikes, burst density (what laughter and applause look like), and silence→explosion payoff shapes. Visual gives scene cuts, motion, and face-area changes." Signals are binned at 1 second and "normalized within that video". "Where real audience data exists (Twitch chat replay measured by unique chatters, YouTube's most-replayed heatmap), it adds a small capped bonus." The LLM sees the transcript plus an event timeline. "Because small models score everything in a narrow band, the finalists then get compared head-to-head in one rerank call: relative judgment is much easier for a 7B model than absolute scoring." — [ColinGPT9/clips-studio](https://github.com/ColinGPT9/clips-studio)
- JayWebtech/autoshorts warns: "local models are generally not recommended for viral moment detection. Smaller 3B/7B models lack the context reasoning and mathematical capabilities needed to evaluate long transcripts and calculate accurate segment timestamps (often outputting fragments that are too short)". It defaults to DeepSeek or Claude, with Deepgram transcription — [JayWebtech/autoshorts](https://github.com/JayWebtech/autoshorts)
- OpenShorts.app: "Google Gemini 3.0 Flash analyzes transcripts and scene boundaries to detect 3-15 high-potential moments", with PySceneDetect for scene boundaries — [faris-sait/openshorts](https://github.com/faris-sait/openshorts)
- hotclip (Chinese, AGPL-3.0, 470 stars, pushed 2026-10-26) uses "弹幕热度" (danmaku/chat heat) to judge peak moments in livestream replays, alongside AI quote detection — [xixihhhh/hotclip](https://github.com/xixihhhh/hotclip)
- clipify (Claude Code skill, 664 stars, MIT) scans a Whisper transcript "for punchlines, reversals, awkward pauses, and audio peaks to propose 3–5 candidates" — [louisedesadeleer/clipify](https://github.com/louisedesadeleer/clipify)
- viral-clips-crew (CrewAI) notes: "Gemini can process videos up to 1 hour in length. If you are using the OpenAI API, please ensure that the clip is less than 15 minutes" (dated context-window guidance; last push 2026-02-16) — [alexfazio/viral-clips-crew](https://github.com/alexfazio/viral-clips-crew)
- ClipsAI's ClipFinder segments transcripts without an LLM and is designed for "audio-centric, narrative-based videos such as podcasts, interviews, speeches, and sermons" — [ClipsAI/clipsai](https://github.com/ClipsAI/clipsai)
- PySceneDetect: 5,504 stars, pushed 2026-11-16, BSD-3 — [Breakthrough/PySceneDetect](https://github.com/Breakthrough/PySceneDetect)
- auto-editor (5,939 stars, pushed 2026-11-16, Unlicense) cuts by audio loudness/motion: default `--edit audio:threshold=0.04`, `--edit motion:threshold=0.02`, combinable `--edit "(or audio:0.03 motion:0.06)"`, `--margin 0.2sec`, and export to Premiere/Resolve etc. It is useful for dead-air removal inside a clip — [WyattBlue/auto-editor](https://github.com/WyattBlue/auto-editor)
- FunClip supports LLM-assisted clipping and SenseVoice audio-event detection (e.g. laughter/applause events) — [modelscope/FunClip](https://github.com/modelscope/FunClip)
- publikclip advertises "A virality score you can audit — never a bare number". Scoring runs on its own "publik API" by default, with Gemini or Ollama ("reduced scoring quality") as options — [Blueturboguy07/publikclip](https://github.com/Blueturboguy07/publikclip)

### Inferences
- Illustrative LLM contract. Send `[[t_start, t_end, speaker, text], ...]` in chunks of about 20–30 min with overlap, plus a per-second signal summary (chat msgs/sec z-score, RMS loudness z-score, laughter events, scene cuts). Ask for strict JSON `{start, end, hook_text, title, score_0_100, reason, needs_context:boolean}`, with constraints such as 15–60 s, starting on a sentence boundary, and the first 3 s containing the hook. Then snap start/end to word boundaries from the word timestamps (LLMs misreport timestamps), dedupe overlaps, and do a pairwise or top-k rerank pass. These are the patterns the strongest repos above converge on.
- For Twitch specifically, chat-replay spikes (unique chatters per window, emote bursts like "LUL", "KEKW", "Pog") are a strong, cheap prefilter. Run the LLM only on the top windows instead of the full VOD transcript.

### Gaps
- I found no rigorous public evaluation showing that LLM "virality scores" predict real view counts. publikclip's optional "real-outcomes loop" via Instagram is the only feedback-loop design I found.
- I didn't find a maintained open-source laughter-detection model to cite (beyond FunClip's SenseVoice audio events).

## 4. Reframing to 9:16 (face/person tracking, smoothing, split-screen, blur fill)

### Takeaway
Standard stack: PySceneDetect splits shots; per shot, MediaPipe (face) and/or YOLOv8 (person) detection decides between TRACK (crop window follows the subject) and LETTERBOX/blur-fill (keep the full frame). The crop path is smoothed within a shot and hard-cut between shots/speakers. Speaker-aware cropping uses diarization (pyannote) or active-speaker detection (TalkNet). Gaming/stream clips use a facecam-over-gameplay split via ffmpeg `vstack`. Google AutoFlip (MediaPipe) is a 2020-era research framework that's no longer prominent; a small 2026 Python port exists.

### Cited Findings
- Autocrop-vertical (463 stars, pushed 2026-02-15, no license file): PySceneDetect → YOLOv8 people + Haar faces on each scene's middle frame → per-scene TRACK or LETTERBOX → OpenCV reads every frame and pipes raw frames to FFmpeg. "Scene detection is the dominant bottleneck (~50% of total time)". `--encoder hw` auto-detects VideoToolbox/NVENC. A bug fix noted that FPS mismatch (29.97 vs 30) between PySceneDetect and OpenCV caused A/V drift, fixed with `-vsync cfr` — [kamilstanuch/Autocrop-vertical](https://github.com/kamilstanuch/Autocrop-vertical)
- OpenShorts.app: "Dual-mode AI reframing — TRACK mode (MediaPipe + YOLOv8 face tracking) and GENERAL mode (blurred background)", with FFmpeg compositing of ASS subtitles and hook overlays — [faris-sait/openshorts](https://github.com/faris-sait/openshorts)
- Clips Kitty: "YOLOv8 pose detection keeps the subject centred", and in group footage follows "whoever is actually speaking, decided by TalkNet active-speaker detection from the face and the audio together". "When the speaker changes the framing cuts to them instead of panning across". It has a "webcam + game" layout for Gaming/Reaction and a ball-following crop for sports — [ColinGPT9/clips-studio](https://github.com/ColinGPT9/clips-studio)
- ViralCutter: Auto-Crop 9:16, "Split Screen Inteligente" (detects 2 people and splits the screen), experimental Active Speaker. It uses insightface (needs C++ build tools on Windows), WhisperX and Hormozi-style captions, and exports Premiere XML. GPL-3.0, 462 stars, pushed 2026-09-10 — [RafaelGodoyEbert/ViralCutter](https://github.com/RafaelGodoyEbert/ViralCutter)
- ClipsAI's `resize(video_file_path, pyannote_auth_token, aspect_ratio=(9,16))` uses pyannote diarization to focus on the current speaker — [ClipsAI/clipsai](https://github.com/ClipsAI/clipsai)
- podcli: face tracking with split-screen layouts. "Following the active speaker needs AssemblyAI, or a source install with openai-whisper and HF_TOKEN". It also has loudness normalization and NVENC/VideoToolbox — [nmbrthirteen/podcli](https://github.com/nmbrthirteen/podcli)
- MediaPipe repo is now google-ai-edge/mediapipe (37,717 stars, pushed 2026-11-16, Apache-2.0). Google says support for MediaPipe Legacy Solutions (including the old `mp.solutions.face_detection`) ended March 1, 2023, replaced by the Tasks API `FaceDetector` — [google-ai-edge/mediapipe](https://github.com/google-ai-edge/mediapipe); [MediaPipe Solutions guide](https://developers.google.com/edge/mediapipe/solutions/guide)
- AutoFlip is referenced in the MediaPipe README only as a blog link ("AutoFlip: An Open Source Framework for Intelligent Video Reframing"). The old `docs/solutions/autoflip.md` path now returns 404. pyautoflip (24 stars, pushed 2026-11-15, MIT) is "A Python library for saliency-aware video cropping" — [MediaPipe README](https://github.com/google-ai-edge/mediapipe); [Google Research blog](https://research.google/blog/autoflip-an-open-source-framework-for-intelligent-video-reframing/); [AhmedHisham1/pyautoflip](https://github.com/AhmedHisham1/pyautoflip)
- Ultralytics (YOLO26/YOLO27/YOLO11/YOLOv8) is **AGPL-3.0** (63,490 stars), which matters for a hosted SaaS — [ultralytics/ultralytics](https://github.com/ultralytics/ultralytics)
- KazKozDev/auto-vertical-reframe: "Auto-reframe CLI for vertical 9:16 video — keeps the subject in frame with YOLO tracking" (MIT) — [KazKozDev/auto-vertical-reframe](https://github.com/KazKozDev/auto-vertical-reframe)
- Split-screen layout guidance: about 60/40 top/bottom for gameplay + facecam. A Hugging Face clipbot builds a 1080x1920 canvas with the main video in the top 65% and gameplay in the bottom 35%, using `vstack` — [Hugging Face clipbot app.py](https://huggingface.co/spaces/imspsycho/clipbot-ffmpeg/blob/main/app.py); [clipspeed vertical guide](https://clipspeed.ai/blog/vertical-video-editing-guide.html); [ottverse stacking](https://ottverse.com/stack-videos-horizontally-vertically-grid-with-ffmpeg/)

### Inferences
- Illustrative blurred-background fill (16:9 → 1080x1920), not from a verified source:
  ```
  ffmpeg -i in.mp4 -filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:2[bg];[0:v]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2" -c:a copy out.mp4
  ```
- Illustrative facecam-top / gameplay-bottom split. Facecam rectangle coordinates come from the streamer's layout or a one-time face detection:
  ```
  ffmpeg -i in.mp4 -filter_complex "[0:v]crop=480:270:1440:810,scale=1080:768[cam];[0:v]crop=ih*1080/1152:ih,scale=1080:1152[game];[cam][game]vstack=inputs=2[v]" -map "[v]" -map 0:a out.mp4
  ```
- Smoothing: sample detections at about 5–10 fps, interpolate, then apply an exponential moving average or one-euro filter on the crop center, with a dead-zone so the frame doesn't jitter. Reset at scene cuts and on speaker changes (hard cut). Render either by piping per-frame crops through OpenCV, as Autocrop-vertical does, or with ffmpeg `sendcmd`/expression-driven crop for piecewise-constant crops.
- License caution: Ultralytics AGPL and many AGPL clippers (Clips Kitty, hotclip, publikclip, ViralMint, podcli) have network-use obligations for a hosted service. MediaPipe (Apache-2.0) is the permissive option for face detection.

### Gaps
- No benchmark comparing MediaPipe vs YOLO face/person tracking quality for gaming streams (small facecams, overlays).
- I couldn't retrieve AutoFlip's current build status. The doc path 404s, which suggests it was removed from the docs tree, but I didn't confirm whether the code still builds.

## 5. Animated captions (ASS karaoke, pycaps, Remotion, MoviePy, drawtext)

### Takeaway
Two practical routes. (a) Generate an ASS file from word timestamps (one Dialogue line per word or per 2–4-word page, with `\k`/`\kf` karaoke or per-word color/scale `\t` animation) and burn it with ffmpeg `-vf ass=...`. This is the fastest, fully headless route and what most Python clippers use. (b) Use HTML/CSS/React renderers (pycaps via Playwright, Remotion with `@remotion/captions`) for richer Hormozi/MrBeast styling, at higher render cost. Remotion needs a paid company license for companies with 4+ employees.

### Cited Findings
- ASS karaoke specifics: `\k` durations are in **centiseconds** (seconds × 100) while `\t` animation times are in milliseconds, a frequent source of drift. `\k` fills, `\kf` sweeps, `\ko` highlights the outline. For vertical video set `PlayResX: 1080`, `PlayResY: 1920`. Burn in with `ffmpeg -i video.mp4 -vf "ass=subtitles.ass" output.mp4` — [JosiahSiegel ffmpeg-kinetic-captions skill](https://claudskills.com/skills/ffmpeg-kinetic-captions/SKILL.md); [dev.to: auto-highlighting subtitles for Shorts](https://dev.to/wcamon/we-built-auto-highlighting-subtitles-for-youtube-shorts-heres-the-130-line-python-that-does-it-50ee); [dev.to: Whisper+FFmpeg Node worker](https://dev.to/kyle_clipspeedai/auto-caption-generation-whisper-ffmpeg-in-a-nodejs-worker-53b0)
- pycaps (233 stars, pushed 2026-09-30, MIT, "very alpha", not on PyPI): CSS-styled subtitles rendered via Playwright/Chromium (`CssSubtitleRenderer`) or the lighter browserless `PictexSubtitleRenderer` (subset of CSS). Features: templates, `.word-being-narrated` selector, word tagging by regex/lists/AI, animations (fades, pops, slides), and effects including "typewriting, emoji insertion, sound effects". CLI: `pycaps render --input my_video.mp4 --template minimalist [--transcript transcript.json]`. Accepts whisper_json/srt/vtt transcripts — [francozanardi/pycaps](https://github.com/francozanardi/pycaps)
- Remotion `createTikTokStyleCaptions({captions, combineTokensWithinMilliseconds})` groups word tokens into pages; a low value gives word-by-word animation. `breakOnSilenceAfterMilliseconds` (v4.0.514+) and `pageBreakAfter` (v4.0.517+) control paging. Text must include a leading space per word and should render with `white-space: pre` — [Remotion docs source: createTikTokStyleCaptions](https://github.com/remotion-dev/remotion/blob/main/packages/docs/docs/captions/create-tiktok-style-captions.mdx)
- remotion-dev/template-tiktok (308 stars, pushed 2026-11-09) "Generate TikTok-style captions with Whisper.cpp" and downloads the 1.5GB `medium.en` model by default — [remotion-dev/template-tiktok](https://github.com/remotion-dev/template-tiktok)
- Remotion: 73,629 stars, pushed 2026-11-16. License: free for individuals, for-profits with up to 3 employees, and non-profits. A Company License is required otherwise. Remotion 5.0 will change license terms slightly — [remotion-dev/remotion LICENSE](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md)
- captacity (Whisper + MoviePy captions for Shorts) was last pushed 2024-06-07 (141 stars) and is stale. auto-subtitle (2,302 stars) was last pushed 2024-07-12 and is stale — [unconv/captacity](https://github.com/unconv/captacity); [m1guelpf/auto-subtitle](https://github.com/m1guelpf/auto-subtitle)
- MoviePy is active (15,153 stars, pushed 2026-08-26, MIT). FunClip v2.2.1 replaced ImageMagick/MoviePy TextClip with a Pillow renderer: "standard subtitle clipping no longer requires ImageMagick" — [Zulko/moviepy](https://github.com/Zulko/moviepy); [modelscope/FunClip](https://github.com/modelscope/FunClip)
- ViralCutter offers Hormozi-style word-by-word highlight with colors and emojis. clipify's `build_ass.py` generates "opus/karaoke/minimal ASS captions from whisper JSON". publikclip offers "karaoke highlighting". The AutoShorts gameplay clipper uses PyCaps — [ViralCutter](https://github.com/RafaelGodoyEbert/ViralCutter); [clipify](https://github.com/louisedesadeleer/clipify); [publikclip](https://github.com/Blueturboguy07/publikclip); [divyaprakash0426/autoshorts](https://github.com/divyaprakash0426/autoshorts)
- Small 2026 ASS-karaoke generators exist (sebetancurch/auto-caption "CapCut-style karaoke captions … Whisper word timestamps + animated ASS"; DorXmoon/karaoke-subs) but have very low adoption (13 and 0 stars) — [sebetancurch/auto-caption](https://github.com/sebetancurch/auto-caption); [DorXmoon/karaoke-subs](https://github.com/DorXmoon/karaoke-subs)

### Inferences
- Illustrative ASS for a Hormozi-style "active word pops yellow" (one Dialogue per word, page text repeated with the current word overridden):
  ```
  [Script Info]
  PlayResX: 1080
  PlayResY: 1920
  [V4+ Styles]
  Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
  Style: Cap,Montserrat ExtraBold,90,&H00FFFFFF,&H0000FFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,0,2,60,60,520,1
  [Events]
  Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
  Dialogue: 0,0:00:01.20,0:00:01.48,Cap,,0,0,0,,THIS {\c&H00FFFF&\fscx115\fscy115}IS{\r} INSANE
  ```
  (ASS colours are &HBBGGRR, so `&H00FFFF&` is yellow.) Burn with `-vf "ass=caps.ass:fontsdir=./fonts"`. A pure-karaoke alternative is a single line per page: `{\k28}THIS {\k31}IS {\k55}INSANE` with SecondaryColour as the pre-highlight color.
- Emoji: libass can render color emoji only with a suitable font (e.g. Noto Color Emoji) and fontconfig. pycaps' emoji-insertion effect or Remotion/HTML renderers are more reliable for emoji. This is unverified and should be tested.
- Cost/perf ordering (inferred): ASS+libass in the same ffmpeg encode pass is nearly free. drawtext per word is workable but verbose. pycaps/Playwright and Remotion render frames in a headless browser, which is slower but gives full CSS/React animation.

### Gaps
- No primary libass documentation was fetched for `\k` semantics. Sources are blogs/skill pages, though they agree with each other.
- I couldn't fetch Remotion's company license pricing page (remotion.dev blocked).

## 6. Existing open-source "Opus Clip clone" repos (status Nov 2026)

### Takeaway
The space exploded in 2025–2026. Many new repos are local-first desktop apps (Tauri/Electron) or Claude Code skills/plugins. Several 2023–2024 pioneers are abandoned (ClipsAI, Reelsfy, captacity, auto-subtitle, the original OpenShorts fork, tdollar15's clone). The most-starred "clipper" (AI-Youtube-Shorts-Generator) defaults to a paid third-party API (MuAPI), with local mode as an option. The most feature-complete stream-oriented open-source clipper found is Clips Kitty (AGPL-3.0): Twitch/Kick/YouTube input, chat-replay signals, TalkNet speaker crop, webcam+game layout.

### Cited Findings (stars / last push / license as of 2026-11-16)
- **Anil-matcha/AI-Youtube-Shorts-Generator** (formerly SamurAIGPT; its README still clones from the SamurAIGPT URL) — 6,148 / 2026-11-12 / MIT. YouTube URL → ranked 9:16 shorts. Default `--mode api` uses MuAPI for download, transcription, ranking and cropping. `--mode local` uses yt-dlp + faster-whisper + ffmpeg/OpenCV face tracking with an OpenAI or Gemini LLM. It has JSON output, batch mode and a Python API `generate_shorts(...)` — [repo](https://github.com/Anil-matcha/AI-Youtube-Shorts-Generator)
- **ColinGPT9/clips-studio ("Clips Kitty")** — 275 / 2026-11-16 / AGPL-3.0. Windows app plus Docker and CLI. Input: YouTube, Twitch VOD (with chat replay), Kick VOD or local file. Pipeline: faster-whisper large-v3-turbo; multimodal scoring with a local Ollama (Gemma) or OpenRouter LLM; YOLOv8 + TalkNet crop; captions, translation/dubbing in 19 languages; NVENC/AMF/QSV; publishing to YouTube/TikTok/IG. Claims "38 clips from one video in 19 minutes" on one PC — [repo](https://github.com/ColinGPT9/clips-studio)
- **modelscope/FunClip** — 6,566 / 2026-11-01 / MIT. Gradio app built on FunASR (Paraformer, SenseVoice, MOSS diarize). Supports LLM-assisted clipping, speaker-targeted clipping and a Pillow subtitle renderer. Strongest for Chinese — [repo](https://github.com/modelscope/FunClip)
- **RayVentura/ShortGPT** — 8,176 / **2025-02-10** / MIT. A faceless-shorts automation framework (script, TTS via ElevenLabs/EdgeTTS, Pexels stock, MoviePy), not a long-video clipper. Stale — [repo](https://github.com/RayVentura/ShortGPT)
- **harry0703/MoneyPrinterTurbo** — 143,976 / 2026-11-16 / MIT. Topic/keyword → generated short video (faceless), not clipping — [repo](https://github.com/harry0703/MoneyPrinterTurbo)
- **ClipsAI/clipsai** — 574 / **2024-01-17** / MIT. Library for transcript-based clip finding (WhisperX) and pyannote speaker-aware resize. **Abandoned** — [repo](https://github.com/ClipsAI/clipsai)
- **eddieoz/reels-clips-automator (Reelsfy)** — 235 / **2023-09-23** / MIT. GPT + Whisper + face tracking. **Abandoned** — [repo](https://github.com/eddieoz/reels-clips-automator)
- **alexfazio/viral-clips-crew** — 772 / 2026-02-16 / MIT. CrewAI agents. Needs OpenAI + Gemini keys — [repo](https://github.com/alexfazio/viral-clips-crew)
- **RafaelGodoyEbert/ViralCutter** — 462 / 2026-09-10 / GPL-3.0. Gradio WebUI, WhisperX, Gemini/GPT/local GGUF, split-screen, Hormozi captions, Premiere XML export. README is Portuguese-first, with Windows .bat installers using `uv` — [repo](https://github.com/RafaelGodoyEbert/ViralCutter)
- **faris-sait/openshorts (OpenShorts.app)** — 341 / 2026-04-17 / MIT. FastAPI + Gemini 3.0 Flash + faster-whisper + PySceneDetect + MediaPipe/YOLOv8 + ASS. The `mutonby/openshorts` URL no longer resolves; `mutonby/openshorts-plugin` (52 / 2026-10-19 / MIT) is a Claude plugin version — [repo](https://github.com/faris-sait/openshorts); [plugin](https://github.com/mutonby/openshorts-plugin)
- **jipraks/yt-short-clipper** — 1,086 / 2026-09-20 / MIT. Windows Tauri v2 + Python sidecar. AI highlight detection from YouTube's own subtitle track (no Whisper), MediaPipe face tracking, word-by-word captions — [repo](https://github.com/jipraks/yt-short-clipper)
- **JayWebtech/autoshorts** — 1,551 / 2026-11-13 / no license. Tauri 2 + React + Rust + SQLite. Deepgram transcription, DeepSeek/Claude ranking, optional Ollama+Whisper offline. Center-crop only — [repo](https://github.com/JayWebtech/autoshorts)
- **xixihhhh/hotclip** — 470 / 2026-10-26 / AGPL-3.0. Chinese livestream/podcast slicer using danmaku heat; publishes to Douyin/Kuaishou/Bilibili — [repo](https://github.com/xixihhhh/hotclip)
- **divyaprakash0426/autoshorts** — 209 / 2026-11-05 / Apache-2.0. Gameplay-footage clipper: AI scene selection, PyCaps captions, NVENC, optional voiceover (6GB+ VRAM) — [repo](https://github.com/divyaprakash0426/autoshorts)
- **Blueturboguy07/publikclip** — 72 / 2026-11-11 / AGPL-3.0. Tauri, auditable scores, active-speaker crop, music/SFX with ducking. Default scoring goes through the vendor's API — [repo](https://github.com/Blueturboguy07/publikclip)
- **fralapo/clippyme** — 66 / 2026-10-14 / MIT. Self-hosted, Gemini + Whisper/Deepgram/ElevenLabs, MediaPipe + YOLOv8, React dashboard — [repo](https://github.com/fralapo/clippyme)
- **nmbrthirteen/podcli** — 91 / 2026-11-03 / AGPL-3.0. Podcast clipper as CLI + MCP server, whisper.cpp, loudness normalization, NVENC — [repo](https://github.com/nmbrthirteen/podcli)
- **louisedesadeleer/clipify** — 664 / 2026-08-24 / MIT. Claude Code skill: Whisper → candidates → cut → 9:16 → ASS captions — [repo](https://github.com/louisedesadeleer/clipify)
- **opus-pro/opus-skills** — 32 / 2026-10-16 / MIT. The *official* OpusClip agent skill: clip and post via OpusClip's service, not self-hosted — [repo](https://github.com/opus-pro/opus-skills)
- Other 2026 entrants: ayush-that/jiang-clips (338, Remotion-based captions, last push 2026-03-18), openclaw-easy/ViralMint (203, AGPL), GrepCut/OpenClipper (19), kleZ799/clipmint (45), hajdu-patrik/clippy (35), SamurAIGPT/ai-clipping-generator (122, Next.js SaaS template), Anil-matcha/ai-clipping-comfyui (38, ComfyUI nodes) — [GitHub search "opus clip"](https://github.com/search?q=opus+clip&type=repositories); [jiang-clips](https://github.com/ayush-that/jiang-clips); [ViralMint](https://github.com/openclaw-easy/ViralMint)
- Twitch-specific older tools are mostly abandoned or compile Twitch *clips* rather than VODs: pelledrijver/twitch-highlights (2023), viniciusenari/twitch-highlights-bot (2025-04), VadlapatiKarthik/autoclipper (2025-05, YouTube/Twitch/Kick live highlight detection) — [twitch-highlights](https://github.com/pelledrijver/twitch-highlights); [autoclipper](https://github.com/VadlapatiKarthik/autoclipper)
- Opus Clip and competitor pricing per Clips Kitty's table: Opus Clip $15 Starter / $29 Pro; Klap $29 Pro; Vizard $29 Creator — [ColinGPT9/clips-studio](https://github.com/ColinGPT9/clips-studio)

### Inferences
- No single permissively licensed (MIT/Apache) repo combines Twitch/Kick partial download, chat-spike detection, speaker-aware crop with facecam/gameplay layouts, and animated captions. Clips Kitty comes closest but is AGPL and Windows-first. A custom pipeline built from permissive parts (yt-dlp, faster-whisper/WhisperX, PySceneDetect, MediaPipe, ffmpeg+ASS) plus an LLM is the realistic path. Borrow ideas from Clips Kitty's scoring (per-video normalization, capped chat bonus, pairwise rerank).
- Many "open-source" clippers route their key step through a vendor API by default (MuAPI, publik API, tscaps API). Check the default config before assuming a tool is fully local.

### Gaps
- I couldn't find a repo literally called "Frame" that is an Opus-Clip-like tool. The named lookup failed, so the coordinator's reference may be to a different project.
- Star counts are a weak quality signal. Several 2026 repos have obvious star-solicitation, e.g. Clips Kitty's "Goal: 275". I didn't test any repo end-to-end.

## 7. Rendering & infrastructure (encode settings, loudness, NVENC, Remotion Lambda)

### Takeaway
Render 1080x1920, H.264 High, yuv420p, constant 30/60 fps, AAC 48 kHz, MP4 with `+faststart`. Use about 10 Mbps for 1080p30 (YouTube's official guidance; 15 Mbps for HFR). Normalize to about -14 LUFS integrated with a -1 dBTP ceiling. YouTube's -14 is well established, but TikTok and Instagram don't publish targets. NVENC is widely used in clippers with CPU fallback. Remotion Lambda costs cents per clip, plus a company license for teams of 4+.

### Cited Findings
- YouTube recommended upload settings: MP4 container, "no Edit Lists", "moov atom at the front of the file (Fast Start)", variable bitrate, 4:2:0 chroma. 1080p 10 Mbps (standard frame rate) / 15 Mbps (high frame rate). 720p 6.5 / 9.5 Mbps. 1440p 20 / 30 Mbps. "no bitrate limit is required". H.264 High Profile is stated by third-party guides but wasn't confirmed in the official snippet — [YouTube Help 1722171](https://support.google.com/youtube/answer/1722171?hl=en); [soundstripe](https://www.soundstripe.com/blogs/youtube-video-formats)
- Loudness: YouTube (including Shorts) normalizes to about -14 LUFS (downward only, per one source). TikTok and Instagram don't publish targets. Sources variously say -14 to -16 LUFS, about -16, or "-12 to -10". The common recommendation is -14 LUFS integrated, -1 dBTP. One project (browser-use/video-use) uses two-pass ffmpeg loudnorm at I=-14, TP=-1, LRA=11 in its final render — [OpenClip LUFS by platform](https://openclip.app/learn/audio-normalization); [dev.to LUFS -14 for Reels/TikTok/Shorts](https://dev.to/arthurvalle1_a2586dd2b4bc/mastering-for-reels-tiktok-and-youtube-shorts-the-lufs-14-standard-2ck5); [instagit video-use loudnorm](https://instagit.com/browser-use/video-use/how-loudness-normalization-integrates-with-final-render/)
- NVENC usage in clippers: Clips Kitty test-encodes with NVENC/AMF/QSV and falls back to CPU. podcli has VideoToolbox + NVENC with CPU fallback. Autocrop-vertical `--encoder hw` auto-detects NVENC or VideoToolbox but defaults to libx264 "for best quality/compatibility" — [clips-studio](https://github.com/ColinGPT9/clips-studio); [podcli](https://github.com/nmbrthirteen/podcli); [Autocrop-vertical](https://github.com/kamilstanuch/Autocrop-vertical)
- Clips Kitty GPU transcription "also needs NVIDIA's cuBLAS 12" (CTranslate2 dependency) — [clips-studio](https://github.com/ColinGPT9/clips-studio)
- Remotion Lambda cost examples (2048MB RAM, 10240MB disk, us-east-1, Remotion 4.0.381): Hello World about $0.001. A 1-min video embedding a video file costs $0.017 warm / $0.021 cold. A 10-min remote HD video costs $0.103 warm / $0.108 cold (about 56–61s wall). A 10-s 4K video costs about $0.013–0.014. Extra costs: S3 egress/storage, CloudWatch, and "Teams of 4+ people also need to acquire a Remotion Company License". "Rendering a video inside your video increases the cost significantly." — [Remotion docs source: Lambda cost example](https://github.com/remotion-dev/remotion/blob/main/packages/docs/docs/lambda/cost-example.mdx)

### Inferences
- Illustrative final render, combining crop/blur, ASS captions, loudness and encode in one pass:
  ```
  ffmpeg -ss 5083.2 -to 5131.9 -i src.mp4 -filter_complex "[0:v]<reframe graph>,ass=caps.ass,fps=30,format=yuv420p[v];[0:a]loudnorm=I=-14:TP=-1:LRA=11[a]" -map "[v]" -map "[a]" -c:v libx264 -profile:v high -preset medium -crf 20 -maxrate 12M -bufsize 24M -g 60 -c:a aac -b:a 192k -ar 48000 -movflags +faststart out.mp4
  ```
  NVENC variant: `-c:v h264_nvenc -preset p5 -tune hq -rc vbr -cq 21 -b:v 10M -maxrate 15M -bufsize 30M -profile:v high`. For exact loudness, run loudnorm twice: a first pass with `print_format=json`, then feed `measured_I/TP/LRA/thresh` into the second.
- At Remotion's quoted rates, a 45-s caption overlay clip lands on the order of $0.01–0.02 of Lambda compute (extrapolated from the 1-min example). A self-hosted ffmpeg+ASS render costs effectively nothing beyond the box. Remotion's main advantages are design flexibility and parallelism, not cost.
- Keep the source frame rate if it's 60 fps (gaming), since it's a supported upload rate. Otherwise force constant 30 fps to avoid VFR drift (cf. Autocrop-vertical's 29.97-vs-30 A/V drift bug).

### Gaps
- No official TikTok or Instagram documentation was found for upload bitrate or loudness targets. Values are secondary and conflicting.
- Remotion company license price wasn't retrievable (remotion.dev blocked in this session).
- No measured NVENC-vs-x264 quality numbers at short-form bitrates were collected.
