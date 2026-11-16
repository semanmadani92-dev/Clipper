# Twitch Data Sources & APIs: Chat (Live + VOD) and Clip/VOD Video Capture (state as of Nov 2026)

> Method note: dev.twitch.tv and discuss.dev.twitch.com could not be fetched directly from this research environment (DNS blocked). Official Helix endpoint text was therefore taken from (a) DmitryScaletta/twitch-api-swagger, an unofficial OpenAPI spec auto-generated from the dev.twitch.tv reference page (downloaded 2026-11-16), and (b) the twitch-rs `twitch_api` Rust crate source, which copies the official doc strings. Both agree with each other. Forum/changelog facts come from search-engine summaries of discuss.dev.twitch.com pages; treat those as second-hand. Tool internals (TwitchDownloader, chat-downloader, yt-dlp, streamlink, rustlog) were read directly from their GitHub source on 2026-11-16.

## Q1. Live chat: IRC over WebSocket vs EventSub `channel.chat.message`

### Takeaway
Two official live-chat read paths exist: legacy Twitch IRC (wss://irc-ws.chat.twitch.tv, still supported, with a `tmi-sent-ts` millisecond timestamp tag, and anonymous `justinfan` reads still used by tools) and EventSub `channel.chat.message`, which Twitch recommends. EventSub needs `user:read:chat` (+`user:bot`, and `channel:bot` from the broadcaster for app tokens) and has per-connection subscription caps. IRC is not scheduled for removal, but new features go only to EventSub. A 100-channel concurrent-join limit (since May 2024) applies to both paths unless the account is the broadcaster or a moderator.

### Cited Findings
- Twitch's migration guide recommends bots use EventSub to read chat and the Twitch API to send it. IRC RECONNECT and PING/PONG have no equivalent when EventSub is delivered over webhooks — [Twitch: Migrating from Twitch IRC](https://dev.twitch.tv/docs/chat/irc-migration/)
- Twitch launch announcement ("Available today: Twitch Chat on EventSub, an API for sending chat, and the Conduit transport"): "no plan to remove IRC as a third-party supported interface, but… investment in new features will primarily focus on… EventSub and the Twitch API." I found no announced IRC shutdown date as of Nov 2026 — [Twitch Dev Forums announcement](https://discuss.dev.twitch.com/t/available-today-twitch-chat-on-eventsub-an-api-for-sending-chat-and-the-conduit-transport-method-for-eventsub/54596); [Twitch IRC migration doc](https://dev.twitch.tv/docs/chat/irc-migration/)
- Earlier IRC deprecation: most chat *commands* (e.g. /ban, /timeout) stopped working over IRC on or about Feb 18, 2023 and must be done through Helix. Reading messages was not affected — [Deprecation of chat commands through IRC](https://discuss.dev.twitch.com/t/deprecation-of-chat-commands-through-irc/40486)
- TwitchIO (Python) removed IRC from its core library and now uses EventSub only (v3.x) — [TwitchIO FAQ](https://twitchio.dev/en/latest/getting-started/faq.html)
- EventSub `channel.chat.message` auth: a user access token needs `user:read:chat` (plus `user:bot`). An app access token also needs `channel:bot` from the broadcaster, unless the chatting user is a moderator — [EventSub Chat reference](https://dev.twitch.tv/docs/eventsub/reference/chat); [IRC migration guide](https://dev.twitch.tv/docs/chat/irc-migration/)
- EventSub WebSocket limits: 300 enabled subscriptions per connection and a total cost of 10, per client-ID + user-ID pair. WebSocket subscriptions need a user access token, not an app token. No more than 3 subscriptions may share the same type and condition — [Handling WebSocket Events](https://dev.twitch.tv/docs/eventsub/handling-websocket-events); [Managing Subscriptions](https://dev.twitch.tv/docs/eventsub/manage-subscriptions/)
- Large-scale chat reading uses webhooks or Conduits with app tokens, which are not bound by the per-WebSocket caps. Conduits were introduced at the same launch as chat-on-EventSub — [Twitch Dev Forums announcement](https://discuss.dev.twitch.com/t/available-today-twitch-chat-on-eventsub-an-api-for-sending-chat-and-the-conduit-transport-method-for-eventsub/54596)
- Concurrent join limit: lowered in phases from Feb 28, 2024 to **100 channels** on May 15–16, 2024. It applies to both IRC and EventSub chat. The verified-bot exemption was later removed. Joining as the broadcaster or as a moderator does not count. Apps can go beyond the limit with broadcaster authorization (`channel:bot`) — [Giving broadcasters control; concurrent join limits for IRC and EventSub](https://discuss.dev.twitch.com/t/giving-broadcasters-control-concurrent-join-limits-for-irc-and-eventsub/54997); [Twitch Chat docs](https://dev.twitch.tv/docs/irc)
- IRC JOIN rate limits per official docs: 20 join attempts per 10 seconds for regular accounts and 2,000 per 10 seconds for verified accounts, which are "rarely granted" — [Twitch Chat & Chatbots](https://dev.twitch.tv/docs/irc)
- `tmi-sent-ts` is an IRCv3 message tag on PRIVMSG/USERNOTICE carrying the server send time in Unix **milliseconds** — [search summary of Twitch IRC docs/libraries](https://dev.twitch.tv/docs/irc)
- Anonymous read-only IRC is still used in practice. xenova/chat-downloader's live Twitch mode connects to IRC with `NICK justinfan67420` (no OAuth) — [chat-downloader twitch.py](https://github.com/xenova/chat-downloader/blob/master/chat_downloader/sites/twitch.py)
- Official Twitch docs say users must authenticate for the chat client to read and write chat. The anonymous `justinfan` login is **not documented** by Twitch — [Twitch Chat docs (via search summary)](https://dev.twitch.tv/docs/irc)
- Libraries: tmi.js (Node, IRC); twurple (Node, both EventSub and chat); TwitchLib (.NET; `TwitchLib.Api.Helix.Clips` and others); twitchio (Python, EventSub-only from v3); twitch-rs/twitch_api (Rust, implements all four Clips endpoints, including 2025–26 additions) — [TwitchIO FAQ](https://twitchio.dev/en/latest/getting-started/faq.html); [TwitchLib Clips class ref](https://twitchlib.github.io/class_twitch_lib_1_1_api_1_1_helix_1_1_clips.html); [twitch-rs clips mod.rs](https://github.com/twitch-rs/twitch_api/blob/main/src/helix/endpoints/clips/mod.rs)
- Twitch's Developer Agreement has a general 24-hour storage cap on Twitch Content unless there is authorization (see Q5). A forum thread asks directly whether scraping IRC messages is allowed — [Is it against Twitch TOS or Developer Agreement to scrap IRC messages?](https://discuss.dev.twitch.com/t/is-it-against-twitch-tos-or-developer-agreement-to-scrap-irc-messages/59003)

### Inferences
- For a clipping tool watching a few streamers' chats live: anonymous IRC (justinfan) is the lowest-friction path and gives `tmi-sent-ts` ms timestamps. EventSub `channel.chat.message` is the "blessed" path. It needs a bot account token with `user:read:chat`, and for more than 100 channels, broadcaster `channel:bot` grants or moderator status.
- Map a live chat message to a VOD offset as `tmi-sent-ts` − stream `started_at` (Helix Get Streams), or − VOD `created_at`. Expect a few seconds of skew from stream delay and broadcast latency.

### Gaps
- Could not directly read the current EventSub chat reference page to confirm the exact `channel.chat.message` payload fields or the subscription "cost" (it is believed to be 0 when authorized). The forum (search summary) also noted that WebSocket-only setups lack the bot badge.
- No primary source found confirming whether anonymous justinfan connections count against the 100-channel join limit.

## Q2. Past-VOD chat (chat replay)

### Takeaway
No official (Helix) API returns VOD chat. The old Kraken v5 `/v5/videos/:id/comments` "rechat" endpoint has been dead since 2022 (410/404). Every working tool in 2026 uses Twitch's **undocumented, unofficial** first-party GraphQL endpoint `https://gql.twitch.tv/gql` with operation `VideoCommentsByOffsetOrCursor` (persisted-query hash `b70a3591ff0f4e0313d126c6a1502d79a1c02baebb288227c582044aa76adf6a`). Cursor pagination can trip "failed integrity check" errors. Offset-based requests and non-web Client-IDs are the usual workaround. Third-party log archives (justlog/rustlog instances such as logs.ivr.fi) only cover channels they were already logging live.

### Cited Findings
- Kraken (API v5) was decommissioned Feb 28, 2022. Requests afterwards return 404 "This API does not exist" — [Legacy Twitch API v5 shutdown reminder](https://discuss.dev.twitch.tv/t/legacy-twitch-api-v5-i-e-kraken-shutdown-reminder-february-28-2022/36589)
- `/v5/videos/:id/comments` was undocumented/"never supported" for third parties. Tools reported `410 Client Error: Gone` for `https://api.twitch.tv/v5/videos/<id>/comments?cursor=` before the full shutdown. Twitch staff said Helix has never supported VOD chat — [Undocumented kraken /videos/<id>/comments endpoint](https://discuss.dev.twitch.com/t/undocumented-kraken-videos-id-comments-endpoint/36278); [Vod chat for helix](https://discuss.dev.twitch.tv/t/vod-chat-for-helix/33269); [410 error report](https://lightrun.com/answers/petterkraabol-twitch-chat-downloader-410-client-error)
- **TwitchDownloader (lay295), current master** — `ChatDownloader.cs`:
  - POSTs to `https://gql.twitch.tv/gql` with header `Client-ID: kd1unb4b3q4t58fwlpcbzcbnm76a8fp` (not the web client ID `kimne78kx3ncx6brgo4mv6wki5h1ko`).
  - The first request body is `{"operationName":"VideoCommentsByOffsetOrCursor","variables":{"videoID":"<id>","contentOffsetSeconds":<start>},"extensions":{"persistedQuery":{"version":1,"sha256Hash":"b70a3591ff0f4e0313d126c6a1502d79a1c02baebb288227c582044aa76adf6a"}}}`.
  - Later requests replace `contentOffsetSeconds` with `"cursor":"<edges.last.cursor>"` until `pageInfo.hasNextPage` is false.
  - It splits the VOD into N parallel time chunks (`--threads`, default 4), de-duplicates by comment ID, and sorts by offset.
  - It also corrects old VODs whose comments are offset by up to an hour.

  — [TwitchDownloader ChatDownloader.cs](https://github.com/lay295/TwitchDownloader/blob/master/TwitchDownloaderCore/ChatDownloader.cs)
- TwitchDownloader chat JSON (`ChatRoot`):
  - Top level: `{FileInfo, streamer, clipper, video, comments[], embeddedData}`.
  - Each comment: `{_id, created_at (UTC DateTime), channel_id, content_type, content_id, content_offset_seconds (double), commenter{…}, message{body, bits_spent, fragments[], user_badges[], user_color, user_notice_params, emoticons[]}}`.

  — [TwitchDownloader ChatRoot.cs](https://github.com/lay295/TwitchDownloader/blob/master/TwitchDownloaderCore/TwitchObjects/ChatRoot.cs)
- TwitchDownloaderCLI `chatdownload` mode: `-u/--id` (VOD/clip ID or URL), `-o/--output` (`.json`, `.html` or `.txt`), `--compression None|Gzip`, `-b/--beginning`, `-e/--ending` (trim), `-E/--embed-images` (with `--bttv/--ffz/--stv`), `--timestamp-format Utc|UtcFull|Relative|None`, `-t/--threads` (default 4; "Large values may result in IP rate limiting") — [TwitchDownloaderCLI README](https://github.com/lay295/TwitchDownloader/blob/master/TwitchDownloaderCLI/README.md)
- xenova/chat-downloader (Python) uses the same GQL operation and hash with Client-ID `kd1unb4b3q4t58fwlpcbzcbnm76a8fp`. The web client ID `kimne78kx3ncx6brgo4mv6wki5h1ko` is commented out in its source. It uses anonymous IRC (justinfan) for live streams — [chat-downloader twitch.py](https://github.com/xenova/chat-downloader/blob/master/chat_downloader/sites/twitch.py)
- Integrity issues:
  - A write-up reports that paging with the cursor returns "failed integrity check", enforced only for requests that use the web Client-ID.
  - Vendors and other projects report offset-based paging avoids the integrity challenge. One vendor post claims this was live-verified on 2026-05-16.
  - ZetHor3/TwitchChatDownloader scans in 30-second offset windows to avoid cursor blocks.
  - TwitchVODEnhancer claims a browser-generated Client-Integrity token is needed.

  These are unofficial, partly vendor-marketing sources — [Jordan Ryyan write-up](https://www.jordanmryyan.com/posts/Training-a-Language-Model-to-Mimic-Twitch-Chat-Part-1-vv); [DEV.to vendor post](https://dev.to/devil_scrapes/twitch-chat-scraper-export-any-vods-full-chat-replay-for-1051k-1jea); [ZetHor3/TwitchChatDownloader](https://github.com/ZetHor3/TwitchChatDownloader); [TwitchVODEnhancer](https://github.com/mmrry/TwitchVODEnhancer)
- yt-dlp's Twitch extractor (current master) no longer has any "rechat"/chat-subtitle code. Its GQL hash table covers only metadata and clip operations. Use TwitchDownloader or chat-downloader for VOD chat — [yt-dlp twitch.py](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/twitch.py)
- Archives:
  - rustlog is a justlog-compatible Twitch chat logger (Clickhouse storage). Its web API routes include:
    - `/channels`
    - `/list`
    - `/{channel_id_type}/{channel}/{year}/{month}/{day}` (daily channel log)
    - `/{channel_id_type}/{channel}/{user_id_type}/{user}/{year}/{month}`
    - `/…/search`, `/…/stats`, `/…/random`
    - `/namehistory/{user_id}`
    - `/optout`
    - `/docs` (Scalar UI) and `/openapi.json`
  - Query flags include `json`, `json_basic`, `raw`, `ndjson`, `reverse`, `limit` and `offset`. `channel_id_type` is `channel` (login) or `channelid`.
  - It only logs channels configured on that instance (`/channels` lists them).

  — [rustlog README](https://github.com/boring-nick/rustlog/blob/master/README.md); [rustlog src/web/mod.rs](https://github.com/boring-nick/rustlog/blob/master/src/web/mod.rs); [rustlog schema.rs](https://github.com/boring-nick/rustlog/blob/master/src/web/schema.rs); [gempir/justlog](https://github.com/gempir/justlog)
- logs.ivr.fi is a public justlog/rustlog-style instance. I found no primary documentation of its channel coverage. A historical comparison point: OverRustle Logs shut down over legal issues around sharing logs — [search summary: StreamScheme](https://www.streamscheme.com/twitch-chat-logs/); [Twitch forum: How to Access Users Full Chat Logs?](https://discuss.dev.twitch.tv/t/how-to-access-users-full-chat-logs/30221)
- Twitch staff (forum): "There is no API endpoint for getting historic chat data." — [Twitch dev forum (search summary)](https://discuss.dev.twitch.tv/t/how-to-access-users-full-chat-logs/30221)

### Inferences
- For "chat spike → clip" on past VODs, the practical pipeline is TwitchDownloaderCLI `chatdownload --id <vod> -o chat.json` (or chat-downloader). Then bin `content_offset_seconds` into a histogram. Offsets are already VOD-relative, so no clock alignment is needed.
- The GQL hash and Client-ID can be rotated by Twitch at any time. Pin a tool version and monitor its GitHub issues. Prefer recording chat live (IRC/EventSub) for channels you care about, so you don't depend on GQL.
- Persisting chat logs of channels you don't have authorization from sits in grey territory under the Developer Agreement's 24-hour storage rule (see Q5).

### Gaps
- Could not confirm whether the `b70a3591…` hash is still valid in Nov 2026. It is present in current master of both TwitchDownloader and chat-downloader, but I couldn't check either repo's issue tracker.
- No primary source found for logs.ivr.fi's channel list or retention policy.
- No current information found on tcd (PetterKraabol Twitch-Chat-Downloader). Its last known failure mode was the v5 410 error, which suggests it has been abandoned or was rewritten.

## Q3. Helix Clips API (Create Clip, Create Clip From VOD, Get Clips, Get Clips Download)

### Takeaway
As of Nov 2026, Helix has four clip endpoints:
- **POST /helix/clips** (Create Clip from live stream; scope `clips:edit`). It now accepts optional `title` and `duration` (5–60 s, 0.1 s precision, default 30).
- **POST /helix/videos/clips** (NEW, "Create Clip From VOD"; `editor:manage:clips` or `channel:manage:clips`). It clips an arbitrary offset in a VOD, including earlier in the current live stream, but only on behalf of the broadcaster or a channel editor.
- **GET /helix/clips** (metadata).
- **GET /helix/clips/downloads** (NEW, "Get Clips Download"; open beta Sept 2025, then GA). It returns `landscape_download_url`/`portrait_download_url`, again only for broadcaster/editor tokens, and is rate-limited to 100 req/min.

Max clip length is 60 s.

### Cited Findings
- **POST https://api.twitch.tv/helix/clips** (Create Clip):
  - Needs a user access token with `clips:edit`.
  - Query params: `broadcaster_id` (required), `title` (optional), and `duration` ("The length of the clip in seconds. Possible values range from 5 to 60 inclusively with a precision of 0.1. The default is 30.").
  - Window: "This API captures up to 90 seconds of the broadcaster's stream. The 90 seconds spans the point in the stream from when you called the API. For example, if you call the API at the 4:00 minute mark, the API captures from approximately the 2:35 mark to approximately the 4:05 minute mark." By default Twitch publishes up to the last 30 s of that window.
  - Creation is asynchronous: poll Get Clips by the returned ID, and "If after 60 seconds Get Clips hasn't returned the clip, assume it failed."
  - Response: `{id, edit_url}`. `edit_url` is valid up to 24 h or until the clip is published.

  — [twitch-api-swagger (auto-generated from dev.twitch.tv reference)](https://github.com/DmitryScaletta/twitch-api-swagger); [twitch-rs create_clip.rs](https://github.com/twitch-rs/twitch_api/blob/main/src/helix/endpoints/clips/create_clip.rs); [twitch-rs clips mod.rs (CreatedClip)](https://github.com/twitch-rs/twitch_api/blob/main/src/helix/endpoints/clips/mod.rs)
- The older `has_delay` query param, described in Twitch's clips guide as adding a delay before capture, is no longer listed in the current generated reference. The guide still mentions it — [Twitch Clips guide (search summary)](https://dev.twitch.tv/docs/api/clips/); compare [twitch-api-swagger](https://github.com/DmitryScaletta/twitch-api-swagger)
- **POST https://api.twitch.tv/helix/videos/clips** (Create Clip From VOD, marked "NEW"):
  - "Creates a clip from a broadcaster's VOD on behalf of the broadcaster or an editor of the channel. Since a live stream is actively creating a VOD, this endpoint can also be used to create a clip from earlier in the current stream."
  - Auth: an app or user access token with `editor:manage:clips` or `channel:manage:clips`.
  - Params:
    - `editor_id` (required; must match `user_id` in the token)
    - `broadcaster_id` (required)
    - `vod_id` (required)
    - `vod_offset` (required; "zero-based offset, in seconds, to where the clip should **end**")
    - `duration` (optional, 5–60 s, 0.1 precision, default 30)
    - `title` (required)
  - The clip spans `[vod_offset − duration, vod_offset]`, so `vod_offset` must be ≥ `duration`.
  - `edit_url` allows editing the title, featuring, creating a portrait version, downloading, and sharing to social platforms.

  — [twitch-api-swagger](https://github.com/DmitryScaletta/twitch-api-swagger); [twitch-rs create_clip_from_vod.rs](https://github.com/twitch-rs/twitch_api/blob/main/src/helix/endpoints/clips/create_clip_from_vod.rs)
- A forum reply from January 2026 states that the Create Clip changes (title/duration) were released and links to Create Clip From VOD docs. A separate thread reports that `edit_url` opens the clip page rather than the editor. Another feature request asks for a captions parameter, which does not exist yet — [Create Clip From VOD Response Link](https://discuss.dev.twitch.com/t/create-clip-from-vod-response-link/64538); [captions feature request](https://discuss.dev.twitch.com/t/feature-request-optional-captions-parameter-for-create-clip-create-clip-from-vod-and-a-way-to-edit-a-clip-after-creation/65254)
- **GET https://api.twitch.tv/helix/clips/downloads** (Get Clips Download, marked "NEW"):
  - "Provides URLs to download the video file(s) for the specified clips… These links are temporary."
  - Rate limit: **100 requests per minute**.
  - Auth: an app or user token that includes `editor:manage:clips` or `channel:manage:clips`.
  - Params: `editor_id` (required, must match token user), `broadcaster_id` (required), and `clip_id` (repeatable, max **10**).
  - Response items: `{clip_id, landscape_download_url (nullable), portrait_download_url (nullable)}`.

  — [twitch-api-swagger](https://github.com/DmitryScaletta/twitch-api-swagger); [twitch-rs get_clips_download.rs](https://github.com/twitch-rs/twitch_api/blob/main/src/helix/endpoints/clips/get_clips_download.rs)
- Get Clips Download launched in open beta in Sept 2025, with GA announced "in two weeks". Twitch staff said that "streamers should have control over who can download their content which is why scopes are necessary" and that there are no plans to add file URLs to Get Clips — [Twitch Dev Forums announcement](https://discuss.dev.twitch.com/t/get-clips-download-twitch-api-endpoint-now-available-in-open-beta/64334); [Zach Bussey (Threads)](https://www.threads.com/@zachbussey/post/DOzQ05uDzzv/twitch-has-launched-a-get-clips-download-api-endpoint-in-open-beta-and-will-make)
- A developer reports that Get Clips Download returns 1080p60 H.264 (~7.5 Mbps) `landscape_download_url` files even for clips from a 1440p HEVC stream, so source quality is not always available — [Forum thread](https://discuss.dev.twitch.com/t/get-clips-download-returns-1080p-h-264-for-clips-from-a-1440p-hevc-stream-is-source-quality-available/65261)
- **GET https://api.twitch.tv/helix/clips**:
  - Any app or user token.
  - Params: `broadcaster_id` | `game_id` | `id` (mutually exclusive; up to 100 IDs), `started_at`/`ended_at` (RFC3339; the default window is start + 1 week), `first` (≤100, default 20), `before`/`after`, `is_featured`.
  - Pagination caps at ~1,000 results total, so split by time windows.
  - Clip fields: `id, url, embed_url, broadcaster_id/name, creator_id/name, video_id, game_id, language, title, view_count, created_at, thumbnail_url, duration, vod_offset, is_featured`. `vod_offset` is null until set (there is a delay after live clip creation).

  — [twitch-api-swagger](https://github.com/DmitryScaletta/twitch-api-swagger)
- Unofficial download routes for clips from other people's channels: the old "thumbnail_url → .mp4" trick, plus GQL operations. yt-dlp still carries a `ShareClipRenderStatus` GQL hash for clip media, and TwitchDownloader/streamlink download clips through GQL — [yt-dlp twitch.py](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/twitch.py); [Get twitch clip download link (forum)](https://discuss.dev.twitch.com/t/get-twitch-clip-download-link/21164)

### Inferences
- **Clipping a VOD at an arbitrary offset via API is officially possible only with broadcaster or editor authorization** (Create Clip From VOD). A third-party clipper with no channel relationship can still use POST /helix/clips (`clips:edit`, any viewer's token) on a *live* stream. It captures only around "now", with `duration` ≤60 s ending near the call time. It cannot target past offsets, and the official download URL requires broadcaster/editor scopes.
- A compliant "spike → clip" product therefore works best as a streamer-authorized app: the streamer (or a mod added as editor) grants `channel:manage:clips`/`editor:manage:clips`. The app detects chat spikes, calls POST /helix/videos/clips with `vod_offset = spike_time + tail`, then GET /helix/clips/downloads for the MP4 (landscape and portrait).
- Live Create Clip clips end at roughly call time + ~5 s, so trigger detection must fire within the 90 s window.

### Gaps
- Could not read the official dev.twitch.tv changelog to get exact dates for (a) the `title`/`duration` additions to Create Clip, (b) the Create Clip From VOD launch, or (c) Get Clips Download GA. Best evidence: the download endpoint went to open beta in Sept 2025 and Create Clip changes landed around Jan 2026.
- Rate limits for Create Clip and Create Clip From VOD were not found beyond the general Helix token-bucket (commonly 800 points/min per token). The figure is not verified here.
- Could not confirm whether the official reference still describes `has_delay`, or whether Create Clip From VOD works on sub-only or muted VOD segments.

## Q4. Video capture: VOD segments, live recording, markers, retention

### Takeaway
There is no official API to download VODs. Every VOD or live-video download tool (yt-dlp, streamlink, TwitchDownloader) uses the **unofficial** GQL `PlaybackAccessToken` plus the Usher HLS playlist (`usher.ttvnw.net`). yt-dlp `--download-sections "*HH:MM:SS-HH:MM:SS"` grabs time ranges from VODs. TwitchDownloaderCLI `videodownload -b/-e` does the same, with exact trimming. streamlink records live streams and can rewind via `--hls-live-restart`/`--hls-start-offset` within whatever the live playlist exposes. Sub-only VODs need the user's OAuth token. Retention:
- Past broadcasts: 7 days (regular), 14 days (Affiliates), 60 days (Partners/Turbo/Prime).
- Highlights/uploads: a 100-hour cap (from May 2025).

Stream markers (Helix) are an official way to bookmark moments for later.

### Cited Findings
- yt-dlp Twitch extractor:
  - Uses `_USHER_BASE = 'https://usher.ttvnw.net'` and GQL `…PlaybackAccessToken`.
  - Default Client-ID is `ue6666qo983tsx6so1t0vnawi233wa`, overridable with `--extractor-args "twitch:client_id=…"`.
  - Supports login (netrc machine `twitch`) for sub-only content.

  — [yt-dlp twitch.py](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/twitch.py)
- Partial VOD download example: `yt-dlp "https://www.twitch.tv/videos/<id>" --download-sections "*02:34:30-02:34:50"`. It requires ffmpeg and can be repeated for multiple sections — [VideoHelp forum](https://forum.videohelp.com/showthread.php?p=2768027); [yt-dlp download options](https://mintlify.com/yt-dlp/yt-dlp/cli/download-options)
- TwitchDownloaderCLI `videodownload`: `-u/--id`, `-o`, `-q/--quality` (e.g. `1080p60`), `-b/--beginning`, `-e/--ending`, `-t/--threads` (default 4), `--bandwidth` (KiB/s), `--trim-mode Exact|Safe`, and `--oauth` ("OAuth access token to download subscriber only VODs") — [TwitchDownloaderCLI README](https://github.com/lay295/TwitchDownloader/blob/master/TwitchDownloaderCLI/README.md)
- streamlink Twitch plugin:
  - Uses Client-ID `kimne78kx3ncx6brgo4mv6wki5h1ko` and the Usher service (`usher.ttvnw.net`) for channels and VODs.
  - It may need a **client-integrity token**, which it acquires by launching a web browser (Chromium CDP) when the access-token request fails. Options: `--twitch-force-client-integrity` and `--twitch-purge-client-integrity`.
  - Other options: `--twitch-api-header` / an OAuth alias for sub-only content, `--twitch-access-token-param`, `--twitch-low-latency`, `--twitch-supported-codecs h264,h265,av1`.

  — [streamlink twitch.py](https://github.com/streamlink/streamlink/blob/master/src/streamlink/plugins/twitch.py); [streamlink Twitch plugin docs](https://streamlink.github.io/cli/plugins/twitch.html)
- streamlink generic HLS options: `--hls-live-restart` ("skip to the beginning of a live stream, or as far back as possible") and `--hls-start-offset [HH:]MM:SS` (can be negative from the live edge on live streams). How far back a live rewind can go depends on the playlist window Twitch serves — [streamlink man page](https://mankier.com/1/streamlink); [tldr streamlink](https://tldr.dendron.so/notes/common.streamlink.html)
- twitch-dlp (npm) supports section downloads and `--live-from-start` for ongoing streams. Its docs note retention limits on hidden VODs — [twitch-dlp README](https://cdn.jsdelivr.net/npm/twitch-dlp@0.6.3/README.md)
- Helix Get Videos:
  - Fields include `stream_id`, `created_at`, `published_at`, `type` (`archive`/`highlight`/`upload`), `duration` (e.g. `3m21s`), `viewable`, and `muted_segments` ("The segments that Twitch Audio Recognition muted; otherwise, null"; items have `duration` and `offset`).
  - Query by `id` (≤100), `user_id` or `game_id`, with an app or user token.

  — [twitch-api-swagger](https://github.com/DmitryScaletta/twitch-api-swagger)
- **Create Stream Marker**:
  - POST `/helix/streams/markers`, user token with `channel:manage:broadcast`.
  - Body `{user_id, description (≤140 chars)}`.
  - Fails if the stream is not live, VOD is disabled, or the stream is a rerun.
  - **Get Stream Markers**: GET `/helix/streams/markers?user_id=|video_id=` with `user:read:broadcast` or `channel:manage:broadcast`. The caller must own the video or be an editor.

  — [twitch-api-swagger](https://github.com/DmitryScaletta/twitch-api-swagger)
- VOD retention: past broadcasts are kept 60 days for Partners/Turbo/Prime and 7 days otherwise, with Affiliates at 14 days (one source said 7 for Affiliates; 14 is better supported). Higher-quality (2K) or vertical renditions expire after 7 days — [Archive Team wiki: Twitch](https://wiki.archiveteam.org/index.php/Twitch); [On Demand Content on Twitch (clipping of help article)](https://anilkeshwani.github.io/garden/Clippings/On-Demand-Content-on-Twitch)
- 100-hour storage cap on Highlights and Uploads (not past broadcasts or clips). It was announced 2025-02-19, with enforcement originally planned for 2025-04-19 and extended to 2025-05-19 — [Tubefilter](https://www.tubefilter.com/2025/02/20/twitch-highlights-100-hours-limit/amp/); [AlternativeTo news](https://alternativeto.net/news/2025/2/twitch-introduces-100-hour-storage-limit-for-highlights-and-uploads-starting-april-2025); [GamesRadar](https://www.gamesradar.com/games/a-really-sad-day-for-speedrunning-the-worlds-fastest-gamers-brace-for-brace-for-a-new-twitch-storage-limit-on-all-highlights-and-uploads)
- A Twitch forum thread says there is no official way to programmatically download your own VODs (or anyone's) — [Downloading own VOD from CDN — ToS violation?](https://discuss.dev.twitch.com/t/downloading-own-vod-from-cdn-tos-violation/64652)

### Inferences
- Muted segments (from `muted_segments`) are silent in the downloaded HLS. Avoid clipping across them, or warn the user. Twitch audio recognition is a strong signal that the section contains copyrighted music.
- For live spike-clipping without streamer auth, a rolling local buffer (streamlink to a segmenting ffmpeg, keeping the last N minutes) gives arbitrary-length capture around a chat spike. It relies on unofficial Usher access and possibly integrity tokens.
- Stream markers only let the broadcaster or an editor bookmark moments (`channel:manage:broadcast`). They pair naturally with Create Clip From VOD in a streamer-authorized tool.

### Gaps
- Could not verify the current Usher playlist window for live rewind on Twitch (how many minutes `--hls-live-restart` can reach).
- No primary Twitch help-center text was retrievable to confirm the 14-day Affiliate retention figure.

## Q5. Terms of Service / Developer Agreement / copyright constraints

### Takeaway
Official APIs (Helix, EventSub, IRC) are permitted under the Developer Services Agreement (DSA). GQL (`gql.twitch.tv`) and Usher are undocumented, and the DSA bars accessing undocumented Program Materials without written permission. The consumer ToS also bans scraping and circumventing access controls, so GQL chat/VOD downloading is unofficial and ToS-risky. Storing Twitch Content is limited to 24 hours unless authorized; OAuth consent from the user/streamer is the staff-endorsed basis for longer storage. Reposting another streamer's content to TikTok/YouTube is not covered by Twitch's license (except Twitch's own share features) and needs the streamer's permission, plus attention to music/DMCA.

### Cited Findings
- DSA: developers may not "access undocumented Program Materials or attempt to derive or use the underlying source code of undocumented Program Materials without Twitch's prior written permission." Copies of Twitch Content may be stored only with written authorization, where the developer controls the rights, or for **up to 24 hours** without sharing with third parties. Re-syndication of API data is prohibited — [Twitch Developer Services Agreement](https://www.twitch.tv/p/en/legal/developer-agreement/)
- Consumer ToS prohibits accessing Twitch by "robot, spider, scraper, or other automated means" and bypassing access-restriction measures — [Twitch Terms of Service](https://www.twitch.tv/p/en/legal/terms-of-service/)
- Twitch staff (forum): if you implement an OAuth flow to get the user's permission to access their data, you are compliant with the DSA to store and present it beyond 24 hours. For edge cases, staff direct developers to developers@twitch.tv or legal@twitch.tv. This is a forum statement, not a contract amendment — [Storage of data from Twitch API](https://discuss.dev.twitch.com/t/storage-of-data-from-twitch-api/63884); [Request for clarification… beyond 24 hours](https://discuss.dev.twitch.com/t/request-for-clarification-prior-written-authorization-for-storing-third-party-viewer-count-data-beyond-24-hours/65105)
- ToS user-content license: the rights a creator grants survive deletion "to the extent you shared it with others as part of the Twitch Services and others copied or stored portions of the User Content (e.g., made a Clip)." The ToS also says the Services "may allow users to access, use, and/or share User Content outside the Twitch Services." — [Twitch Terms of Service](https://www.twitch.tv/p/en/legal/terms-of-service/)
- An April 2025 ToS update added language granting users a license tied to Twitch's new clip "Share" feature (to TikTok/YouTube), which streamers can disable in Clips settings. A later ToS update (per Zach Bussey) changed how Twitch exercises its own content license — [Zach Bussey on X (Apr 2025)](https://x.com/zachbussey/status/1907865287036187037); [Zach Bussey on X (later update)](https://x.com/zachbussey/status/2088007509583724864); [Dexerto on clip sharing to TikTok/YouTube](https://dexerto.com/twitch/new-twitch-clip-feature-could-streamers-in-trouble-with-tiktok-youtube-2904523)
- Twitch staff's rationale for scope-gating Get Clips Download: streamers "should have control over who can download their content." — [Get Clips Download announcement](https://discuss.dev.twitch.com/t/get-clips-download-twitch-api-endpoint-now-available-in-open-beta/64334)
- Streamers can restrict who can clip (e.g. followers-only or subscriber-only, or by category) and can delete viewer clips — [Technipages](https://www.technipages.com/twitch-tv-limit-clips-streams); [GameRevolution: clip permissions](https://www.gamerevolution.com/news/657634-twitch-clip-permissions-added)
- Reposting guidance from a clipping vendor (not legal advice):
  - Twitch's share button is covered when the streamer enables it; downloading and reposting to your own page is not.
  - "Permission for TikTok is not permission for a monetized YouTube channel."
  - US statutory damages run $750–$30,000 per work, and 3 YouTube strikes in 90 days terminates a channel.

  — [Lumina Clippers: Is clipping legal?](https://luminaclippers.com/blog/is-clipping-legal)
- Twitch's DJ program extends to clips, but licensed music does not carry over to clips shared off-platform. Music is the main DMCA risk — [NetInfluencer](https://www.netinfluencer.com/twitch-adds-clips-to-its-dj-program-but-licensed-music-wont-come-along/); [Foxi Music](https://www.foximusic.com/music-licensing-for-twitch-streamers/)

### Inferences
Best practice for a clipping product:
1. Onboard streamers via OAuth (`channel:manage:clips`, `channel:bot` and/or `user:read:chat`, `channel:manage:broadcast`). This puts clip creation, downloads and chat storage on documented APIs, with consent covering storage beyond 24 h.
2. Get explicit written permission (and agree revenue terms) before reposting to monetized YouTube/TikTok.
3. Skip segments listed in `muted_segments` and avoid copyrighted music.
4. Treat GQL chat replay and Usher VOD downloading as unofficial fallbacks that can break or draw enforcement.

### Gaps
- Could not retrieve the full current text of the ToS or DSA (fetch blocked), so I couldn't check for 2026 revisions beyond the X posts cited.
- No official Twitch statement found that specifically addresses third-party "clipping channels" reposting streamers' content.
