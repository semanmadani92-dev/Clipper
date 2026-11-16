# Chat-spike highlight detection for Twitch, YouTube Live and Kick (state as of Nov 2026)

Research notes for building a detector that finds highlights from chat activity and starts clips about 30 s before the spike.

Method note: research ran in a cloud session with restricted network access. github.com and web search worked. arxiv.org, ar5iv.labs.arxiv.org, www2.cs.sfu.ca and vod.ing could not be fetched (DNS blocked). As a result, some paper details come from search-result abstracts and summaries rather than full texts. Those cases are marked. GitHub star counts and dates come from `gh search repos` / GitHub pages fetched on 2026-11-16.

---

## 1. Existing open-source projects (GitHub) for chat-based highlight detection

### Takeaway
No dominant, well-maintained open-source "chat spike to clip" project exists. The space is a long tail of small repos (mostly 0-60 stars), many created in 2025-2026 and often AI-generated. Together they show a clear convergence on one design:
- a rolling-window message or unique-chatter rate,
- a rolling median/MAD (or multiplier-over-baseline) threshold,
- reaction-keyword/emote weighting,
- merging of nearby spikes,
- a fixed pre-roll (about 10-20 s in the repos that document it).

The most mature academic code is dscig/twitch-highlight-detection (emote embeddings + video, 19 stars). The best-documented live algorithm is serdarakbay/hype-clipper (0 stars, but its parameters are explicit).

### Cited Findings

**Explicitly documented chat-spike algorithms (most useful as references)**

- **serdarakbay/hype-clipper** (Python + HTML overlay, MIT, 0 stars, 20 commits; README says "Built with OpenAI Codex"). Live Twitch detector. — [GitHub](https://github.com/serdarakbay/hype-clipper)
  - **Signal:** unique chatters in a rolling 10-second window, compared against a rolling median/MAD baseline.
  - **Warmup:** a 3-minute baseline warmup before any trigger.
  - **Thresholds:** hype-score threshold 3.0 by default. Sensitivity sets the chatter-ratio multiplier: low 3.0x, medium 2.5x (default), high 2.0x.
  - **Session end:** a "session" ends when the score stays below 1.0 for 20 s.
  - **Tiers:** NICE / GREAT / INSANE / LEGENDARY. It makes one clip per session plus at most one "upgrade" clip, which must be at least 2 tiers higher.
  - **Peak waiting:** uses a 3-sample smoothed rate. The clip fires after a 70% drop from the peak or after 8 s with no new peak, with a 60 s hard cap.
  - **Clip length:** from wave start to the Create Clip call, plus 20 s pre-roll, clamped to 5-60 s.
  - **Stream delay:** clips use the Twitch Create Clip `has_delay` flag so they match what viewers saw.
  - **Moment-type labelling:** regex groups over the window's messages. A group needs at least 10% of the window's messages and at least 3 messages; otherwise the label is HYPE.
  - **Documented limitations:**
    - Bot raids of new accounts posting identical text inflate unique-chatter counts.
    - Bulk questions to the streamer caused 1 false positive.
    - Farewell spam at low baselines gets mislabelled FUNNY.
    - Testing covered only 16 clips on 4 channels.
    - The 20 s pre-roll can leave low-action chat-reaction time at the end.
- **Rohi56u/VoXCluTcH** (Python/Flask, 0 stars, 6 commits). Fuses anonymous IRC chat with local VOD audio energy. — [GitHub](https://github.com/Rohi56u/VoXCluTcH)
  - **Window:** a rolling 15-second FIFO window, gated by minimum message and unique-chatter counts (values not stated).
  - **Chat score:** `100 × (0.45·V + 0.35·E + 0.20·R)`, where:
    - V = `min(messages/12, 1)`
    - E = Shannon entropy of per-author message shares, normalized by ln(#authored messages). This rewards many distinct chatters over one spammer.
    - R = reaction messages / total messages. Reaction cues include "pog", "poggers", "letsgo", "clutch", "insane", "hype", "kekw", "lmao", plus elongated laughter patterns.
  - **Audio ("EchoMap"):** FFmpeg extracts mono s16 PCM at 8 kHz and computes per-second RMS dBFS. Each window's peak is compared to the median of a 40 s ambient baseline: `AudioFit = clamp(ΔdB/15 × 100, 0, 100)`.
  - **Final rank:** `0.70·Chat + 0.30·AudioFit`.
  - **Limitations:** stream-to-VOD sync is manual, and pre/post-roll is undocumented.
- **joaohenggeler/twitch-chat-highlights** (Python, 10 stars, 33 commits). — [GitHub](https://github.com/joaohenggeler/twitch-chat-highlights)
  - Splits chat into fixed `bucket_length` buckets and counts messages per user-defined `categories` of words/emotes (plain or `regex:`). The example counts LUL in 20 s windows.
  - `message_threshold`: minimum count for a bucket to qualify.
  - `top_bucket_distance_threshold`: minimum spacing between highlights, in buckets. When highlights are close, it keeps the better-ranked one and discards those with fewer messages.
  - `top_url_delay`: seconds subtracted from the VOD timestamp "to give context". This is effectively a pre-roll.
  - Also supports "positive / negative / controversial" comparison categories.
  - Its chat download relied on the Twitch v5 API, which the README notes was expected to stop working on 2022-02-28. It also includes a live `bot.py` logger.
- **Mica-J7/elowcraft-script** (Streamlit, 1 star, 3 commits). — [GitHub](https://github.com/Mica-J7/elowcraft-script); [search summary](https://github.com/Mica-J7/elowcraft-script)
  - Downloads VOD chat via TwitchDownloaderCLI and video via yt-dlp.
  - Bins messages using a configurable "bin size" and flags spikes over "a rolling baseline" using a "spike threshold".
  - Groups nearby spikes into "moments" and applies a configurable "clip pre/post-roll".
  - No default values are documented. It is Windows-oriented.
- **xurei/twitch-highlights-logger** (JavaScript, 34 stars, 100 commits). Loads the full VOD chat log and counts "the number of messages in a given window of time". It flags a highlight "when the number of messages matching a certain filter reach a threshold". No parameters are documented. — [GitHub](https://github.com/xurei/twitch-highlights-logger)
- **hougesen/twitch-highlight-finder** (Rust, 9 stars, last updated Dec 2025). "Attempts to find Twitch highlights by analysing frequency of chat messages and emotes." — [gh search results](https://github.com/hougesen/twitch-highlight-finder)

**ML / multimodal repos**

- **dscig/twitch-highlight-detection** (PyTorch, 19 stars, 12 commits). Code for "Finding Epic Moments in Live Content through Learning from Collective Decisions" (submitted to EPJ Data Science). — [GitHub](https://github.com/dscig/twitch-highlight-detection)
  - Learns emote embeddings: "the meanings of emoting expressions in a fixed-dimensional vector space". It ships gensim KeyedVectors for the top 1000 emotes.
  - Combines chat with video features in a deep classifier. It reports "detect popular clips with an accuracy of 0.8261" and says combined chat and video features are "critical".
  - The dataset is available only on request.
  - Ground truth is popular Twitch clips, so the crowd's clip choices serve as labels.
- **artkulak/twitch-stream-highlights-detection** (Python/Django, 59 stars, 4 commits). — [GitHub](https://github.com/artkulak/twitch-stream-highlights-detection)
  - Real-time detection with three signals: audio tagging (audioset_tagging_cnn), chat sentiment (transformers), and movement scoring.
  - A logistic-regression metamodel scores fixed 10-second clips.
  - It reports no evaluation metrics, needs a heavy GCP setup, and ships a default credential in its SQLite DB.
- **marianonj/TwitchAutoClipper** (Python, 2 stars, last push 2022-10-31): "suggests highlights based on chat message frequency, content, and audio cues". — [gh search](https://github.com/marianonj/TwitchAutoClipper)
- **Sammers21/twitch-auto-clip-maker** (Java, 0 stars, 2021): makes Twitch clips based on chat reaction. — [gh search](https://github.com/Sammers21/twitch-auto-clip-maker)

**2025-2026 long tail (all 0-3 stars; from gh search on 2026-11-16)**

- sqrtminustwo/twitch_auto_clipper (Python, pushed 2026-09-07): "Automatically create Twitch clips when chat activity spikes". — [gh](https://github.com/sqrtminustwo/twitch_auto_clipper)
- Vladshmalii/twitch-auto-clip-bot (Python, pushed 2026-11-10): "detects Twitch stream highlights from chat velocity, audio and video signals". — [gh](https://github.com/Vladshmalii/twitch-auto-clip-bot)
- teseo/twitch-toolkit (TypeScript, 3 stars, pushed 2026-01-31): VOD highlight detection plus clip extraction. — [gh](https://github.com/teseo/twitch-toolkit)
- sidgaikwad/stream-clipper: records live streams and saves a clip when chat "suddenly gets much busier than normal". It has a sensitivity multiplier and uses an LLM to rate and title clips. — [GitHub](https://github.com/sidgaikwad/stream-clipper)
- PIGJET/autoclipnew: "VOD highlight detector using chat, replay heatmaps, audio analysis, and targeted Whisper transcription". — [GitHub](https://github.com/PIGJET/autoclipnew)
- VadlapatiKarthik/autoclipper: YouTube/Twitch/Kick; uses "audience-retention data, chat spikes and timestamped comments", FFmpeg and Whisper, with a FastAPI + Celery + React stack. — [GitHub](https://github.com/VadlapatiKarthik/autoclipper)
- sheuuar/twitch-chat-analyzer: parses VOD chat logs, "filters out spam", uses "volume-spike algorithms", and outputs HH:MM:SS timestamps (Streamlit). — [GitHub](https://github.com/sheuuar/twitch-chat-analyzer)
- **Kick:** a burst of tiny "kick-clipper" repos pushed Sep-Nov 2026. Examples:
  - dazeb/kickstream-clipper: monitoring daemon using yt-dlp, ffmpeg and a Flask dashboard. — [gh](https://github.com/dazeb/kickstream-clipper)
  - EstebanDevJR/KickClipper: "100% local tool that turns Kick VODs into ready-to-upload content". — [gh](https://github.com/EstebanDevJR/KickClipper)
  - kesit-otomasyon/kick-clipper: live Kick to vertical Shorts. — [gh](https://github.com/kesit-otomasyon/kick-clipper)
- **Compilation bots** (use already-popular clips rather than chat): pelledrijver/twitch-highlights (Python, 42 stars) — [gh](https://github.com/pelledrijver/twitch-highlights); viniciusenari/twitch-highlights-bot (49 stars) — [gh](https://github.com/viniciusenari/twitch-highlights-bot). These rank Twitch's top clips by views and do not detect spikes.

**Commercial products and Twitch native**

- **Twitch "Auto Clips".** Announced at TwitchCon Europe (Rotterdam), 2026. It generates captioned clips from a stream's best moments using "chat activity, vocal inflection, and on-screen events". It is in alpha, English-language channels only, with applications open. — [streamer.guide](https://streamer.guide/blog/twitchcon-rotterdam-2026-new-features-1440p-clips-guilds); [Bleeding Cool](https://bleedingcool.com/pop-culture/twitchcon-europe-2026-reveals-new-updates-coming-to-the-platform/) (via search summary)
- **Twitch voice clipping.** "Twitch, Clip That" voice-activated clipping was rolling out to Partners and Affiliates as of July 2026. Clips go to Clips Manager for review and can be disabled in Clip Settings. — [Gaming Careers newsletter](https://gamingcareers.com/newsletters/twitch-clip-that-actually-works-now/) (via search summary)
- **Eklipse.** Its marketing says it detects "when voice jumps or chat explodes". A third-party writeup says the newer "Gameplay Intelligence" engine analyses gameplay video, audio and chat together. However, an older Eklipse help-center page states the AI does not analyze chat reactions; it focuses on kills, audio cues and on-screen events. These sources conflict. — [Eklipse Roblox page](https://eklipse.gg/use-case/roblox-highlights/); [ai-deck writeup](https://ai-deck.app/blog/eklipse/); contradicted by [Eklipse help](https://eklipse.gg/help/does-the-ai-consider-my-chats-reactions-when-picking-highlights/)
- **Powder.** An Eklipse comparison page says Powder auto-detected about 40 games plus a universal audio-based fallback "before it closed". Another 2026 comparison still lists it, so its status is unresolved. — [Eklipse vs Powder](https://eklipse.gg/compare/eklipse-vs-powder/)
- **StreamLadder.** Primarily manual cutting; its "ClipGPT" now scans full VODs (per competitor page). — [Eklipse vs StreamLadder](https://eklipse.gg/compare/eklipse-vs-streamladder/)
- **Other clip tools.** Klypra claims real-time chat reading for live auto-clipping. Choppity ranks suggested clips by predicted engagement. Both are vendor claims. — [klypra](https://klypra.app/blog/best-ai-tool-to-clip-twitch-streams); [Choppity](https://www.choppity.com/tools/free-ai-clip-maker/twitch-ai-clip-maker/)

### Inferences
- The common pattern across independent projects suggests a robust baseline:
  - unique chatters or messages in a 10-20 s sliding window,
  - median/MAD baseline with a 2-3x multiplier or robust z of about 3,
  - a reaction-keyword ratio,
  - author entropy to resist spam,
  - merging within about 20-30 s,
  - a fixed pre-roll.
- Vendors increasingly treat chat as one signal among audio, game events and transcripts. Twitch's own Auto Clips also blends chat with "vocal inflection" and on-screen events. A chat-only detector will be competitive only if combined with audio and transcript refinement.
- Low star counts mean these repos are useful as design references, not as dependencies.

### Gaps
- Exact last-commit dates for individual repos could not be retrieved (the `gh api repos/...` call was blocked for repos not attached to the session). Dates shown are `pushedAt`/`updatedAt` from search, and `updatedAt` can reflect star activity.
- No public technical details exist for Medal's or Spikes Studio's detection methods; nothing was found in this session.
- Accuracy of Twitch Auto Clips is unknown; there is no independent evaluation.

---

## 2. Academic work on chat-based and multimodal highlight detection

### Takeaway
Academic results consistently find that chat alone is a useful but noisy and lagged signal. Combining chat with video and/or audio improves robustness. The key boundary-placement insight comes from Lightor (ICDE 2020): chat peaks lag the actual moment, so the predicted position must be shifted earlier and refined. Weak labels typically come from journalist-made highlight reels (Fu 2017) or crowd-created Twitch clips (dscig/EPJ).

### Cited Findings
- **Fu, Lee, Bansal, Berg. "Video Highlight Prediction Using Audience Chat Reactions"** (arXiv 1707.08559, 26 Jul 2017; published at EMNLP 2017 as ACL Anthology D17-1102). — [arXiv](https://arxiv.org/abs/1707.08559); [ACL Anthology](https://aclanthology.org/D17-1102/)
  - Data: League of Legends championship broadcasts from North American (NALCS, English chat) and Taiwanese (LMS, traditional Chinese chat) Twitch channels.
  - Ground truth comes from highlight videos made by eSports journalists and fans.
  - Model: multimodal CNN+RNN, with a character-level LSTM-RNN for chat to handle slang, misspellings, emotes and abbreviations.
  - Summary finding: chat alone is not enough for reliable prediction, and chat plus visual models are more robust. — [Liner summary](https://liner.com/review/video-highlight-prediction-using-audience-chat-reactions)
- **Jiang, Qu, Wang, Wang, Zheng. "Towards Extracting Highlights From Recorded Live Videos: An Implicit Crowdsourcing Approach" (Lightor)**, arXiv 1910.12201, ICDE 2020 version hosted by Microsoft Research. — [arXiv](https://arxiv.org/abs/1910.12201v1); [MSR](https://www.microsoft.com/en-us/research/?p=638802); [ICDE PDF](https://www.microsoft.com/en-us/research/uploads/prod/2020/02/icde20lightor.pdf)
  - Highlight Initializer: uses time-stamped chat to predict approximate highlight positions.
  - Highlight Extractor: refines positions iteratively from viewer interaction (seeks/plays around red dots on the progress bar).
  - It notes chat and interaction data are "very noisy".
  - Evaluated on two popular Twitch games with hundreds of MTurk users; achieves "high extraction precision with a small set of training data and low computing resources".
- **dscig, "Finding Epic Moments in Live Content through Learning from Collective Decisions"** (submitted to EPJ Data Science). Learns Twitch emote embeddings plus video. Accuracy 0.8261 for detecting popular clips. A crowdsourced study suggests algorithmic suggestions are "comparable to human decisions". — [GitHub](https://github.com/dscig/twitch-highlight-detection)
- **Ringer, Nicolaou, Walker. "Autohighlight: Highlight detection in League of Legends esports broadcasts via crowd-sourced data"**, Machine Learning with Applications vol. 9, Sep 2022, DOI 10.1016/j.mlwa.2022.100338. — [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2666827022000469); [White Rose eprint](https://eprints.whiterose.ac.uk/186731)
  - Multimodal hybrid-fusion audio-visual architecture.
  - Includes a smoothing step that "brings context into decision making".
  - Weakly supervised, with ranking networks.
- **Ringer's Sheffield PhD thesis "Multi-Modal Livestream Highlight Detection"** includes a chapter on livestream chat. — [White Rose eTheses](https://etheses.whiterose.ac.uk/32406/1/PhD_Thesis__Revised_.pdf)
- **"Deep Unsupervised Multi-View Detection of Video Game Stream Highlights"** (arXiv 1807.09715): unsupervised audio and video for game streams. — [arXiv](https://arxiv.org/html/1807.09715)
- **"A Multimodal Transformer for Live Streaming Highlight Prediction"** (arXiv 2407.12002, 2024). — [arXiv](https://arxiv.org/abs/2407.12002)
  - Targets the live setting, where no future frames are available.
  - Uses images, audio and text comments.
  - Introduces a Modality Temporal Alignment Module for cross-modal time shifts. This is relevant to chat lag.
- **Gutsche (2022 master's dissertation):** pre-trained a transformer language model on League of Legends livestream chat for highlight detection. — [search summary of Autohighlight-related results](https://eprints.whiterose.ac.uk/186731) (only the secondary mention was seen)
- **HiLAIT (Stanford CS231n 2024):** automatic video highlighting using audio and text. — [PDF](https://cs231n.stanford.edu/2024/papers/hilait-automatic-video-highlighting-system-leveraging-audio-text.pdf) (title only seen)

### Inferences
- **Labels.** Twitch's own user-created clips are the cheapest supervision source; dscig did this. A developer can fetch a channel's top clips (with VOD offsets) and use them to tune thresholds and the chat-lag offset per channel.
- **Time alignment.** Lightor and the 2024 Multimodal Transformer both treat temporal misalignment between chat and content as a first-class problem. This supports explicit lag modelling (pre-roll) rather than centering clips on the chat peak.

### Gaps
- Fu et al. per-modality F1 scores, dataset size (number of matches and hours), and any chat-offset handling could not be verified. The arXiv full text was unreachable from this session.
- Lightor's exact numbers (sliding-window length, measured chat-to-highlight lag, precision values) could not be read for the same reason. arxiv.org and www2.cs.sfu.ca were blocked, and the MSR PDF was not fetched.
- Autohighlight precision/recall figures were not retrieved.
- No paper was found that publishes a Twitch emote sentiment lexicon with weights (as opposed to learned embeddings).

---

## 3. Concrete algorithms and parameters

### Takeaway
A robust, implementable detector is a robust-statistics anomaly detector on a per-second activity series. The steps:
1. Compute 1 s buckets, smoothed over 5-15 s.
2. Build a composite score from unique chatters, messages, emote/keyword weight, author entropy and spam/duplicate penalties.
3. Compare against a rolling median + MAD baseline over several minutes, giving a robust z-score.
4. Find peaks with prominence and minimum distance (e.g. `scipy.signal.find_peaks`).
5. Merge peaks closer than about 20-30 s.
6. Rank by peak prominence × duration × reaction-type weight.

Real projects use about 2-3x baseline multipliers or a threshold of about 3 on a robust score, with 3-minute warmups.

### Cited Findings
- **Window and baseline values seen in the wild:**
  - 10 s unique-chatter window, rolling median/MAD, 3-min warmup, threshold 3.0, multipliers 2.0/2.5/3.0x, 3-sample smoothing, end-of-event after 20 s below 1.0. — [hype-clipper](https://github.com/serdarakbay/hype-clipper)
  - 15 s window with min-message/min-unique-chatter gates. — [VoXCluTcH](https://github.com/Rohi56u/VoXCluTcH)
  - 20 s bucket example with a min-spacing parameter in buckets. — [twitch-chat-highlights](https://github.com/joaohenggeler/twitch-chat-highlights)
- **Composite score example:** `0.45·velocity + 0.35·author-entropy + 0.20·reaction-ratio`, with velocity saturating at 12 msgs per 15 s window. Audio fusion: `0.70·chat + 0.30·audio`, where audio = (peak dB − 40 s median dB)/15 dB. — [VoXCluTcH](https://github.com/Rohi56u/VoXCluTcH)
- **Spam and raid robustness:**
  - Counting unique chatters rather than raw messages, and capping each message to count once per category, are the documented countermeasures.
  - Even so, bot raids with identical messages from new accounts still caused false positives. — [hype-clipper](https://github.com/serdarakbay/hype-clipper)
  - Author-entropy weighting penalizes single-user floods. — [VoXCluTcH](https://github.com/Rohi56u/VoXCluTcH)
- **Reaction categorization:**
  - Regex groups with a minimum share (≥10% of window messages and ≥3 messages) label the moment type (FUNNY, HYPE, etc.). — [hype-clipper](https://github.com/serdarakbay/hype-clipper)
  - User-defined categories (e.g. LUL) with "positive / negative / controversial" comparisons. — [twitch-chat-highlights](https://github.com/joaohenggeler/twitch-chat-highlights)
  - Reaction cue list: pog, poggers, letsgo, clutch, insane, hype, kekw, lmao, plus elongated laughter. — [VoXCluTcH](https://github.com/Rohi56u/VoXCluTcH)
- **Learned emote semantics** (embedding vectors for the top 1000 emotes) beat hand lists in the dscig work, as part of a multimodal model. — [dscig](https://github.com/dscig/twitch-highlight-detection)
- **Merging and ranking:** keep the best-ranked bucket within `top_bucket_distance_threshold` and discard nearby lower-count ones (non-maximum suppression). — [twitch-chat-highlights](https://github.com/joaohenggeler/twitch-chat-highlights)
- **`scipy.signal.find_peaks`** supports `height`, `threshold`, `distance` (minimum samples between peaks), `prominence` and `width`. It returns `prominences` and `left_bases`/`right_bases` when `prominence` is given. — [SciPy API reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.find_peaks.html) (standard API; page not fetched in this session)

### Inferences (recommended design; engineering judgment derived from the above)

**Time base.** Use 1 s bins. Per bin compute:
- `msgs`
- `uniq` (distinct user IDs)
- `emote_w` (sum of reaction weights)
- `dup_ratio` (share of messages whose normalized text matches another message in the last 10 s)
- `entropy` (author entropy)

**Normalization across channel sizes.** Use ratios to a robust local baseline, not absolute counts:
- `baseline = rolling_median(x, 300 s)`
- `scale = 1.4826·rolling_MAD(x, 300 s)`, floored at e.g. `max(1, 0.1·baseline)` to avoid divide-by-near-zero in tiny chats
- `z = (x − baseline)/scale`

Also use the ratio `x/baseline` as a second gate, as hype-clipper does with 2-3x.

- **Small channels:** require an absolute minimum (e.g. ≥5 unique chatters in 10 s) so that 1 → 4 messages does not fire.
- **Big channels (>5k chatters):** chat is rate-capped and saturated, so rely more on the reaction-ratio and emote-weight composition.

**EWMA alternative.** For live use, `mean_t = α·x + (1−α)·mean_{t−1}` with α ≈ 2/(N+1), N ≈ 120-300 s, plus EW variance. It is cheap and O(1), but less robust to the spike itself contaminating the baseline. Freeze baseline updates while in an "event" state.

**Emote/keyword weights** (start values; tune per channel). Match case-insensitively on tokens, collapse repeated letters, and count each category once per message:

| Category | Tokens | Weight |
|---|---|---|
| Laughter | KEKW, LUL, OMEGALUL, LULW, ICANT, "LMAO+", "HAHA+", 😂, 💀 | 1.5 |
| Hype | Pog, PogChamp, POGGERS, PogU, "LETS GO+", "W", "clutch", "insane" | 1.5 |
| Shock / fear | monkaS, monkaW, "WTF", "?", "???" | 1.2 |
| Fail | "L", "F", Sadge, "ff" | 1.0 |
| Explicit | "CLIP IT", "clip that", "+clip", "clipped" | 3.0 (strong prior) |
| Sarcasm / low value | Clueless, Copium | 0.5 |

Pull channel-specific 7TV/BTTV/FFZ emote names from the channel's emote sets and learn weights from the channel's historical top clips.

**Spam and copypasta handling:**
- Normalize text (lowercase, strip, collapse repeats).
- Within each 10 s window, count each distinct normalized message at most √n times. Copypasta waves are reactions too, so do not drop them fully.
- Cap each user to 1 message per 2 s.
- Drop known bots (Nightbot, StreamElements, Fossabot, Moobot, etc.).

**Event filtering:**
- Exclude or zero-weight system events: sub/resub/gift-sub notices, bit cheers, raids/hosts, channel-point redemptions, `!commands`, and "first time chatter" greetings.
- After a raid, suppress triggers for about 60-120 s or re-baseline, because chat floods with greetings.
- Hype trains and mass-gift bursts look like spikes; mark them as "event-driven" rather than content highlights.
- These follow from the hype-clipper failure cases (raids, farewell spam, bulk questions).

**Peak finding (offline):**
- Smooth the composite with a 5-10 s centered moving average.
- Call `find_peaks(score, height=3.0, prominence=2.0, distance=30)` (1 s bins means 30 s minimum spacing).
- Take event extent from where the score crosses `0.5·peak` (or `width` with `rel_height=0.5`).

**Merge and rank:**
- Merge events whose extents are within 20-30 s.
- Rank by `prominence × log(1+duration) × (1+reaction_ratio) × explicit_clip_bonus`.
- Then apply non-maximum suppression and take the top-K per hour (e.g. 3-8 per hour for Shorts).

**Live:**
- Keep a state machine: IDLE, then RISING (score > threshold for ≥2 s), then PEAK-WAIT.
- Fire on a 70% drop from the peak or 8 s with no new max (hype-clipper's rule), or a 60 s cap.
- Then apply a cooldown of about 30-60 s.

---

## 4. Chat latency and clip boundaries (pre-roll ~30 s, post-roll, Shorts length)

### Takeaway
The chat peak lags the on-screen moment by:
- the viewer's video latency (a few seconds in Low Latency mode, about 10-15 s in Normal mode),
- plus human reaction and typing time (a few seconds),
- plus the time for chat volume to build to its peak.

Chat timestamps are server-side, but viewers react to delayed video. The cause therefore typically sits about 5-20 s before the peak. Open-source tools use 10-20 s of pre-roll. A 30 s pre-roll measured from the peak (or about 20-30 s from spike onset) is a conservative, reasonable default when the start is then refined with audio and transcript cues.

### Cited Findings
- **Twitch player latency:** Low Latency mode runs "a few seconds" behind; Normal Latency runs about 10-15 s. The player's "Latency to Broadcaster" stat shows per-viewer delay. — [BoostStream](https://booststream.net/blog/twitch-stream-delay) (via search summary)
- **Chat travels faster than video:** chat goes over a separate channel and usually arrives faster than video. — [BoostStream](https://booststream.net/blog/twitch-stream-delay) (via search summary)
- **hype-clipper rationale:** chat reacts about 5-15 s after the event, so it adds 20 s pre-roll and clamps clips to 5-60 s. It notes the cost: the tail may contain low-action reaction time. — [hype-clipper](https://github.com/serdarakbay/hype-clipper); [search summary](https://github.com/serdarakbay/hype-clipper)
- **Twitch Create Clip API `has_delay`:** captures the clip with the broadcaster's stream delay included, so it matches what viewers saw. — [hype-clipper](https://github.com/serdarakbay/hype-clipper)
- **Configurable offset in practice:** `top_url_delay` subtracts seconds from the VOD timestamp to give context before a highlight. — [twitch-chat-highlights](https://github.com/joaohenggeler/twitch-chat-highlights)
- **Practitioner rule of thumb:** the event "usually sits just before the spike", and checking about 10 s around the peak is recommended. — [vod.ing blog](https://vod.ing/blog/find-twitch-highlights-with-chat-activity) (via search summary only; page blocked)
- **Twitch platform clip limits:**
  - API-created clips are capped at 60 s (hype-clipper clamps to 60 s). — [hype-clipper](https://github.com/serdarakbay/hype-clipper)
  - Twitch Auto Clips produce captioned short clips. — [streamer.guide](https://streamer.guide/blog/twitchcon-rotterdam-2026-new-features-1440p-clips-guilds)
- **Audio-energy refinement example:** per-second RMS dBFS against a 40 s median ambient baseline, with a 15 dB full-scale delta. — [VoXCluTcH](https://github.com/Rohi56u/VoXCluTcH)

### Inferences (recommended boundary policy)

**Lag model:** `lag = player_latency (2-15 s) + reaction/typing (2-5 s) + build-up to peak (2-10 s)`. Expected cause-to-peak is about 8-25 s.

- For VODs, chat timestamps from TwitchDownloader/chat-downloader are content offsets as received by the chat server. They are not shifted for viewer latency, so the lag still applies.
- Optionally learn a per-channel lag by cross-correlating the chat-score series with the audio-RMS series over the whole VOD. The argmax over lags of 0-30 s gives the typical delay.

**Default boundaries:**
- `onset` = first second before the peak where the score exceeds about 1.5 robust-z (spike onset).
- `start = onset − 20 s`, which equals roughly `peak − 30 s` for a typical 10 s build-up.
- `end = max(peak + 10 s, time score falls below 1.0) + 3 s`.
- Clamp the total to 20-60 s for Shorts/TikTok and up to 90 s for longer compilations.

**Refinement, after computing a coarse start in [peak−40 s, peak−10 s]:**
1. Snap to a transcript sentence or utterance boundary (Whisper segment start) at or before the coarse start, so the clip does not begin mid-word.
2. Otherwise snap to the nearest audio silence (RMS below the median minus about 10 dB for ≥300 ms) within ±3 s.
3. Look for an audio-energy onset (dB jump of at least 6-10 dB above the 40 s median) in the [peak−25 s, peak] range. If one is found, set the start to about 5-10 s before it for setup context.
4. Snap the end to a sentence end or a silence after the reaction subsides.

**Shorts pacing.** A 30 s pre-roll is long for a short-form hook. Either trim setup so the payoff lands within about the first 3-8 s, or open with a hook (cold open of the reaction) and then cut back. This is editorial judgment; no measured retention data was found in this research.

### Gaps
- No peer-reviewed measurement of the Twitch chat-reaction lag distribution was found. Lightor reportedly models chat lag, but its numbers could not be read (arxiv.org blocked). Values above are estimates from latency docs and tool READMEs.
- Equivalent latency figures for YouTube Live (ultra-low / low / normal latency modes) and Kick were not verified in this session.
- No sourced data was found on optimal TikTok/Shorts clip length for stream clips.

---

## 5. Live (real-time) vs offline (VOD) detection; rolling buffers; reference implementation

### Takeaway
Offline detection is easier:
- the whole chat series is available, so you can use centered smoothing, global or two-sided baselines, `find_peaks` with prominence, and global top-K ranking;
- exact VOD offsets come from TwitchDownloader JSON (`content_offset_seconds`) or chat-downloader.

Live detection must be causal (trailing windows only), so it must fire after the peak with a short wait. It must also clip retroactively, either by:
- calling Twitch's Create Clip API (it captures the preceding stretch of the stream, with `has_delay` to account for the delay), or
- keeping a local ring buffer of the stream (e.g. ffmpeg/streamlink segments covering the last 2-5 min) and cutting `[peak−30 s, peak+15 s]` from it.

### Cited Findings
- **Live projects:**
  - hype-clipper is causal: warmup, then rolling median/MAD, then a wait for peak decay (70% drop or 8 s with no new peak, 60 s cap), then the Twitch Create Clip API with `has_delay`. — [hype-clipper](https://github.com/serdarakbay/hype-clipper)
  - stream-clipper records the live stream itself and cuts clips locally on chat spikes. — [stream-clipper](https://github.com/sidgaikwad/stream-clipper)
  - VoXCluTcH reads anonymous IRC live but cuts from a local VOD, with a manual sync offset. — [VoXCluTcH](https://github.com/Rohi56u/VoXCluTcH)
- **Offline projects:**
  - elowcraft-script uses TwitchDownloaderCLI chat JSON with yt-dlp video. — [elowcraft](https://github.com/Mica-J7/elowcraft-script)
  - twitch-chat-highlights imports saved chat JSON. — [twitch-chat-highlights](https://github.com/joaohenggeler/twitch-chat-highlights)
- **Live models:** must work without future frames. The 2024 multimodal transformer explicitly targets this constraint. — [arXiv 2407.12002](https://arxiv.org/abs/2407.12002)
- **Kick tooling:** recent projects monitor Kick streams via yt-dlp and ffmpeg (e.g. dazeb/kickstream-clipper with a Flask dashboard). — [gh](https://github.com/dazeb/kickstream-clipper)

### Inferences: reference detector (Python, offline; the live variant is noted inline)

```python
import re, math, numpy as np, pandas as pd
from collections import Counter
from scipy.signal import find_peaks

BOTS = {"nightbot","streamelements","fossabot","moobot","streamlabs","sery_bot"}
CATS = {  # weight, regex (tokens); extend with channel 7TV/BTTV/FFZ emotes
  "laugh": (1.5, r"\b(kekw|lulw?|omegalul|icant|lmao+|a?(ha){2,}|xd+)\b|😂|💀"),
  "hype":  (1.5, r"\b(pog(champ|gers|u)?|let'?s ?go+|clutch|insane|w+)\b"),
  "shock": (1.2, r"\b(monka[sw]|wtf|wat)\b|^\?+$"),
  "fail":  (1.0, r"^(l+|f)$|\b(sadge|ff)\b"),
  "clip":  (3.0, r"clip (it|that)|\+clip|clipped"),
}
CATS = {k:(w,re.compile(p,re.I)) for k,(w,p) in CATS.items()}

def norm(t): return re.sub(r"(.)\1{2,}", r"\1\1", t.lower().strip())

def per_second(msgs):  # msgs: DataFrame[t (sec, float), user, text, is_system]
    m = msgs[~msgs.is_system & ~msgs.user.str.lower().isin(BOTS) & ~msgs.text.str.startswith("!")].copy()
    m["sec"] = m.t.astype(int); m["n"] = m.text.map(norm)
    m = m.sort_values("t")
    m = m[m.groupby("user").t.diff().fillna(99) >= 2.0]          # per-user rate cap
    m["w"] = m.text.map(lambda s: sum(w for w,rx in CATS.values() if rx.search(s)))
    T = int(m.sec.max()) + 1
    g = m.groupby("sec")
    df = pd.DataFrame(index=range(T))
    df["msgs"] = g.size(); df["uniq"] = g.user.nunique(); df["emote_w"] = g.w.sum()
    # copypasta dampening: each distinct normalized text counts sqrt(n) per 10 s block
    m["blk"] = m.sec // 10
    damp = m.groupby(["blk","n"]).size().pipe(np.sqrt).groupby(level=0).sum() / m.groupby("blk").size()
    df = df.fillna(0); df["damp"] = (df.index // 10).map(damp).fillna(1.0)
    return df

def robust_z(x, win=300, floor_frac=0.1):
    med = x.rolling(win, min_periods=60).median()      # live: trailing window (causal)
    mad = (x - med).abs().rolling(win, min_periods=60).median() * 1.4826
    scale = np.maximum(mad, np.maximum(1.0, floor_frac * med))
    return ((x - med) / scale).fillna(0), med

def detect(df, pre=30, post=12, min_len=20, max_len=60, min_uniq10=5):
    roll = lambda s, k: s.rolling(k, center=True, min_periods=1).sum()   # live: center=False
    uniq10 = roll(df.uniq, 10); emo10 = roll(df.emote_w, 10); msg10 = roll(df.msgs, 10)
    zu, base = robust_z(uniq10); ze, _ = robust_z(emo10)
    react = (emo10 / msg10.clip(lower=1)).clip(0, 3)
    score = (0.6*zu + 0.4*ze) * df.damp * (1 + 0.3*react)
    score[uniq10 < min_uniq10] = 0                                   # tiny-chat guard
    score = score.rolling(5, center=True, min_periods=1).mean()
    peaks, pr = find_peaks(score.values, height=3.0, prominence=2.0, distance=30)
    events = []
    for p, prom in zip(peaks, pr["prominences"]):
        on = p
        while on > 0 and score.iloc[on-1] > 1.5 and p - on < 45: on -= 1   # spike onset
        off = p
        while off < len(score)-1 and score.iloc[off] > 1.0 and off - p < 30: off += 1
        start = max(0, min(on - 20, p - pre))   # ~30 s before peak, >=20 s before onset
        end = max(p + post, off + 3)
        end = min(max(end, start + min_len), start + max_len)
        events.append(dict(peak=p, start=start, end=end, prom=prom,
                           react=float(react.iloc[p]),
                           rank=prom * math.log1p(off-on+1) * (1 + react.iloc[p])))
    # merge events whose windows overlap or are within 20 s, keep best rank
    events.sort(key=lambda e: e["start"]); merged = []
    for e in events:
        if merged and e["start"] - merged[-1]["end"] < 20:
            a = merged[-1]; best = a if a["rank"] >= e["rank"] else e
            merged[-1] = {**best, "start": min(a["start"], e["start"]),
                          "end": min(max(a["end"], e["end"]), min(a["start"], e["start"]) + 90)}
        else: merged.append(e)
    return sorted(merged, key=lambda e: -e["rank"]), score

# Refinement (after detect): snap e["start"] back to the nearest Whisper segment start in
# [start-5, start+3], else nearest audio silence (RMS < median-10 dB for >=300 ms);
# snap e["end"] forward to the next segment end / silence. Exclude windows overlapping
# raid/hype-train/sub-gift bursts (from USERNOTICE / TwitchDownloader "system" msgs).
```

**Live variant:**
- Same features, but with trailing windows (`center=False`) and an EWMA or ring-buffer median over the last 300 s. Freeze the baseline while in an event.
- Trigger when the score exceeds 3 for ≥2 s and `uniq10 ≥ 2.5×baseline`.
- Wait for the peak to resolve (70% drop or 8 s with no new max, 60 s cap).
- Then either call Twitch Create Clip with `has_delay=true`, or cut `[peak−30, peak+12]` from a local segmented recording (e.g. streamlink, then `ffmpeg -f segment -segment_time 10` with the last 5 min retained).
- Cooldown 45 s; suppress triggers for 90 s after raids.

### Gaps
- No open-source project was found that publishes a labelled evaluation of chat-spike precision/recall against human clips with these parameters. Thresholds above (z≥3, prominence≥2, 30 s distance) are starting points to be tuned against a channel's historical top Twitch clips.
- TwitchDownloader JSON field names (`comments[].content_offset_seconds`, `commenter`, `message.body`, `message.fragments[].emoticon`) and chat-downloader's YouTube/Twitch output formats were not re-verified in this session.
- Kick's chat access path (Pusher websocket vs. the official Kick API launched in 2025) was not verified.
