# Commercial SaaS tools: video link to viral 9:16 clips (state as of Nov 2026)

> Method note: WebFetch to vendor sites (opus.pro, klap.app, clipme.com) was blocked by this session's network policy, so all findings come from WebSearch result synthesis. Official docs pages (help.opus.pro, docs.vizard.ai, docs.submagic.co, docs.reap.video, captions.ai/help) surfaced in search and are cited where search content came from them; many pricing numbers come from third-party review/affiliate blogs (often written by competing clippers) and conflict. Treat every price as "verify on the vendor's pricing page before relying on it." Search-result snippets also flagged that the official OpusClip API overview page was ~126 days old and the limitations page ~168 days old at search time.

## Q1. Per-tool fact base (capabilities from a pasted link, captions, reframing, scoring, B-roll, export/posting, limits, complaints)

### Takeaway
OpusClip, Vizard, Klap, Submagic (Magic Clips), Reap and quso.ai form the "general-purpose link to shorts" tier: paste a URL, get ranked, captioned, auto-reframed 9:16 clips, metered per source minute (or per clip for Klap). Streamer-specific tools (Eklipse, Spikes Studio, StreamLadder, plus newer ClipMe, Klypra, Nexus Clips) differ mainly in Twitch/Kick integration and game/chat signals. Editors (CapCut, Descript, Kapwing, VEED, Riverside, Clipchamp) bolt clipping onto a general editor. Powder has shut down, Munch has pivoted into "Munch Studio", and Captions has rebranded its company as Mirage.

### Cited Findings

**OpusClip (opus.pro)**
- Official help center import sources: Apple Podcast, YouTube, Google Drive, Vimeo, Zoom, Zoom Clips, Rumble, Twitch, Facebook, LinkedIn, X, Dropbox, Riverside, Loom, Frame.io, StreamYard, Kick, Medal.tv, public MP4 URLs, and local uploads up to 10 GB per video. Links must be public or unlisted. — [OpusClip Help: import sources](https://help.opus.pro/docs/article/what-import-sources-does-opusclip-support)
- Recorded Twitch and Kick content imports by link. Clipping a stream while it is live uses "Live Clipping", an Opus Labs private beta that accepts YouTube, Twitch, Kick or TikTok live links. — [OpusClip Help: import sources](https://help.opus.pro/docs/article/what-import-sources-does-opusclip-support); [OpusClip Livestream Clip Maker](https://www.opus.pro/tools/livestream-clip-maker); [OpusClip Kick Clip Maker](https://www.opus.pro/tools/kick-clip-maker)
- Third-party pages say the full list of import sources needs the Pro plan. Not confirmed in the official help article. — [Eklipse: OpusClip alternatives](https://eklipse.gg/compare/opusclip-alternatives/)
- Max input: 10 hours of video and a 30 GB file (API limitations page). — [OpusClip API Limitations](https://help.opus.pro/api-reference/limitation)
- ClipAnything: genre-agnostic moment detection (talking heads, podcast, vlog, gameplay, webinar) using speech, visuals, sound and emotion. It also accepts natural-language prompts such as "find every product demo". — [usefastlane OpusClip review](https://www.usefastlane.ai/review/opusclip); [datastudios](https://www.datastudios.org/post/opus-clip-clipanything-video-repurposing-virality-scoring-and-pricing)
- ReframeAnything: subject-tracking reframe to 9:16, 1:1 or 16:9, described by one source as "alpha". — [techpilot Opus review](https://techpilot.ai/tools/opus-pro-ai-short-clip-generator/)
- Virality score: most sources give a 0–99 scale (one says 0–100), based on hook, pacing and topic shifts. One review discarded about 40% of clips and called the score "a shortlist rather than a predictor". — [datastudios](https://www.datastudios.org/post/opus-clip-clipanything-video-repurposing-virality-scoring-and-pricing); [computertech review](https://computertech.co/opus-clip-review/)
- Captions are animated templates with emoji and keyword highlighting in 20+ languages. AI B-roll and filler/pause removal are listed. — [podposted review](https://www.podposted.com/resources/opus-clip); [frankx workflow](https://www.frankx.ai/blog/ultimate-opus-clip-workflow-2026)
- I found no OpusClip source confirming split-screen (facecam + gameplay) layouts. — (gap; see Gaps)
- Auto-post to YouTube Shorts, TikTok and Instagram Reels from the Starter plan up. Posting to X costs 3 credits per clip per X account. One review says 1 credit instead, a conflict. — [lumiclip](https://www.lumiclip.ai/blog/opus-clip-pricing); [OpusClip API Limitations](https://help.opus.pro/api-reference/limitation); [future-stack-reviews](https://future-stack-reviews.com/opusclip-review/)
- Projects expire after 30 days by default. — [bloggingspark](https://www.bloggingspark.com/klap-api-vs-opusclip-api/)
- Complaints: Reddit r/podcasting users reportedly call the caption editor "fiddly" or "comically bad" for batch edits (relayed by ScaleReach, a competitor). Credits meter uploaded footage, not kept clips, so 90 minutes of footage costs 90 credits even if only 3 clips are usable. A Capterra user said generated clips were "useless… out of context". — [scalereach](https://www.scalereach.ai/blog/opus-clip-review); [prismposter](https://www.prismposter.com/blog/opus-clip-alternatives); [Capterra](https://www.capterra.com/p/10006559/Opus-Clip/reviews)

**Vizard (vizard.ai)**
- The API's `videoType` enum covers 1–14: direct file (mp4/3gp/avi/mov), YouTube (2), Google Drive (3), Vimeo (4), Twitch (9), TikTok, X, Loom, Facebook, LinkedIn, Dropbox and Instagram. Live YouTube is not supported. Kick and Rumble are not listed in the results. — [Vizard API: Submit](https://docs.vizard.ai/reference/submit); [Vizard Minimum Setup](https://docs.vizard.ai/docs/basic)
- Free plan: 60 credits a month (1 credit = 1 source minute), 720p export, watermark, projects expire after 3 days. Uploads are capped at 60 minutes and 1 GB, and one review says exports are capped at 10 minutes. — [layer3labs](https://www.layer3labs.io/guides/vizard-ai-pricing); [openshorts Vizard](https://www.openshorts.app/vizard-ai)
- Creator is $29/month ($14.50/month billed yearly): 4K, no watermark, native scheduling to 6 social accounts. Business is $39/month ($19.50/month billed yearly). Older sources list a $16 Creator price. — [techpilot Vizard](https://techpilot.ai/tools/vizard-ai/); [contenttoolslab](https://contenttoolslab.com/reviews/vizard-ai-pricing/)
- Reviewers often name it the closest workflow match to Opus and praise its processing speed. — [vizard.ai blog (vendor)](https://vizard.ai/blog/9-best-ai-video-clipping-tools-2026); [appscribed](https://appscribed.com/opus-clip-alternatives/)

**Klap (klap.app)**
- Pricing per the official pricing page as relayed: Basic $29, Pro $79 and Pro+ $189 per month, or $174, $474 and $1,134 per year, for 100, 300 and 1,000 clips a month. There is one free video with no card and no ongoing free plan. One review says Klap's live UI now meters input minutes (300/900/2,700) instead, and describes clipping as unlimited. That conflict is unresolved. — [Klap Pricing](https://klap.app/pricing); [valmera Klap review](https://valmera.io/blog/klap-review); [adapter.to](https://adapter.to/blog/how-much-does-klap-cost)
- One review says output quality is lower than Opus on complex audio. — [appscribed](https://appscribed.com/opus-clip-alternatives/)
- API: see Q2.

**Submagic (submagic.co)**
- Primarily a caption-styling tool (animated word-by-word captions, emojis, auto B-roll, zooms). Long-video clipping is "Magic Clips". — [techpilot Submagic](https://techpilot.ai/tools/submagic/); [Submagic API page](https://www.submagic.co/api)
- Plans are $19, $39 and $69 per month ($12, $23 and $41 billed yearly) for 15, 40 and 100 videos a month, billed per member. The top tier is "Business + API". The free trial is 3 watermarked videos. Sources disagree on whether Magic Clips is a separate add-on (about $19/month for 10 uploads) or built in. — [funova](https://funova.ai/en/submagic-review/); [highstyle comparison](https://highstyle.ai/insights/opusclip-vs-submagic-vs-vizard); [cutsnap](https://cutsnap.ai/blog/submagic-pricing-2026)

**Captions.ai / Mirage**
- The company rebranded from Captions to Mirage in September 2025. Mirage Studio (enterprise) launched in June 2025. — [Wikipedia: Captions (app)](https://en.wikipedia.org/wiki/Captions_(app))
- "Clips in Captions" finds and ranks moments "for virality" across podcasts, gaming, webinars and sports, then re-edits them for social. — [Mirage on X](https://x.com/trymirage/status/2100639477173760510); [Mirage on X](https://x.com/trymirage/status/2092645752249913742)
- Consumer pricing is credit-based: Max at $24.99/month for 500 credits, Scale from $69.99 to $279.99/month, and a reported Pro at $9.99/month. Prices listed are iOS prices. — [cutsnap Submagic vs Captions](https://cutsnap.ai/blog/submagic-vs-captions-ai); [storycut](https://www.storycut.com/compare/captions-ai-vs-submagic)
- A third-party status page warns that logging out deletes projects. — [stacksheriff](https://stacksheriff.com/status/captions/)

**Munch**
- getmunch.com redirects to munchstudio.com, which is now an "AI that runs your social media marketing". The self-serve standalone clipper is no longer sold on its own. The redirect dates to April or September 2026 depending on the source. As of October 2026 there is a 7-day trial and no free plan. — [valmera Munch review](https://valmera.io/blog/munch-review); [openshorts GetMunch](https://www.openshorts.app/alternatives/getmunch); [kompozy](https://kompozy.io/reviews/munch)
- Older pricing was about $49/month. — [cutsnap](https://cutsnap.ai/blog/submagic-vs-captions-ai)

**quso.ai (formerly vidyo.ai)**
- Rebranded to quso.ai in January 2025. Plans: Free (75 credits a month), Lite at $29/month or $19 billed yearly, Essential at $39 or $26, Growth at $49 or $33. 1 credit is about 1 minute. — [shortzly](https://shortzly.com/blog/vidyo-ai-alternative); [openshorts vidyo](https://www.openshorts.app/alternatives/vidyo-ai)

**2short.ai**
- Free Starter gives 30 minutes of AI analysis a month. Lite is $9.90/month for 5 hours, Pro $19.90 for 15 hours, Premium $49.90 for 50 hours. All tiers export 1080p with no watermark. YouTube-focused. — [cut.pro](https://cut.pro/en/blog/cheap-ai-clipping-tools-2026); [shortzly 2short](https://shortzly.com/blog/2short-ai-alternative)

**Reap (reap.video)**
- Creator is $24/month or $9.99/month billed yearly ($119.88), with up to 10 hours of clipping. The free plan is 1 hour at 720p. Creator monthly gives 600 credits a month. — [cut.pro](https://cut.pro/en/blog/cheap-ai-clipping-tools-2026); [Reap API docs](https://docs.reap.video/api-reference/1_introduction)
- Reap offers an API, an MCP server and a CLI that share one credit pool (vendor claim). — [Reap MCP](https://reap.video/mcp); [Reap automation blog](https://reap.video/blog/how-to-automate-video-clipping)

**Choppity**
- Sources conflict: Starter at $20/month ($14 billed yearly) with 3 hours of analysis, or $24/month ($16.80 billed yearly) with 1 hour. — [cut.pro](https://cut.pro/en/blog/cheap-ai-clipping-tools-2026)

**Eklipse, StreamLadder, Spikes Studio, Powder, Medal**: see Q3.

**Editors with clip features**
- CapCut: described as the best free option. It offers AI long-video-to-shorts with captions and reframing but no clearly published source-length limit, and moment selection is partly manual. — [ssemble](https://www.ssemble.com/blog/best-ai-clipping-tools-2026); [jupitrr](https://jupitrr.com/best/ai-video-clipping-tools)
- Descript: strongest at text-based editing precision. Clips suit podcasts and interviews. — [autoposting.ai](https://autoposting.ai/blog/ai-video-clipping-tool)
- VEED: browser editor. Free clipping is 10 minutes, paid clipping is unlimited, about $12.25/month per editor billed yearly. — [reap benchmark (vendor)](https://reap.video/reports/state-of-top-ai-video-clipping-tools-2026)
- Riverside Magic Clips: best suited to shows already recorded in Riverside. — [loopdesk](https://loopdesk.ai/blog/best-ai-clipping-tools-2026)
- Kapwing: Free (watermark; free export caps of 1 or 4 minutes depending on source; 10 AI credits total). Pro is $24/month ($16 billed yearly) with 1,000 AI credits a month. Business is $64/month ($50 billed yearly) with 4,000 credits a month. Enterprise is custom. — [fluxnote](https://fluxnote.io/guides/kapwing-pricing-2026); [morphed](https://morphed.app/blog/kapwing-ai-video-generator)
- Clipchamp auto-compose: no 2026 results found (see Gaps).

### Inferences
- Across the general-purpose tools the feature set has converged: animated word-level captions with emoji and keyword highlights, speaker/face-tracking reframe, a 0–99 "virality" score, AI B-roll, and auto-posting. The real differentiators are input sources (OpusClip's list is the broadest and includes Kick, Rumble and Medal), billing unit (source minute vs clip vs video), API availability, and free-tier watermark rules.
- Charging per source minute (OpusClip, Vizard, quso, Reap) makes multi-hour Twitch VODs expensive. A 4-hour VOD is about 240 credits, close to a whole OpusClip Pro month (300). Per-clip billing (Klap) or a VOD-hour token model (Highlight Hunter at about $0.25/hour, see Q3) scales better for streamers.

### Gaps
- Official OpusClip pricing page could not be fetched. Free-plan details (60 credits monthly vs one-time; whether the virality score is visible on Free) conflict across sources.
- I found no confirmation of facecam + gameplay split-screen layouts for OpusClip, Vizard or Klap. StreamLadder and Eklipse are generally known for such layouts, but I found no 2026 citation.
- No 2026 data on Clipchamp auto-compose, Sizzle/Clip.studio or Powder's successors beyond the shutdown. Riverside, CapCut and Descript pricing was not retrieved.
- Max input length for Klap, Submagic, Reap and quso was not found.

## Q2. Which tools have a public developer API (URL in, rendered clips out)? Twitch clip URLs vs full VODs?

### Takeaway
Six vendors offer documented, self-serve URL-to-clips APIs: OpusClip (beta, plan-gated, 1 credit per minute with a 10-credit floor), Vizard (included in paid plans), Klap (pay per operation), Submagic (Magic Clips endpoint, minute packs), Reap (REST + MCP) and Mirage/Captions (gated beta, mostly avatar/caption work, not clipping). OpusClip and Vizard explicitly accept Twitch links. None of the official sources I found distinguishes Twitch clip URLs from full VOD URLs.

### Cited Findings
**OpusClip API**
- Docs are at help.opus.pro/api-reference. Create a project with `POST https://api.opus.pro/api/clip-projects`, a `videoUrl` and `Authorization: Bearer <API_KEY>`. — [OpusClip API Overview](https://help.opus.pro/api-reference/overview); [Create Project](https://help.opus.pro/api-reference/endpoints/create-project); [Quickstart](https://help.opus.pro/api-reference/quickstart)
- Rate limit: 30 requests per minute per API key on the project and clip endpoints (429 when exceeded). Concurrency: 4 simultaneous projects on Pro Beta and Max (429 with header `X-Cap-Reason: concurrent`). — [OpusClip API Limitations](https://help.opus.pro/api-reference/limitation)
- Quota: Pro Beta and Max get 15 hours (900 credits) of API usage per calendar month per workspace. Past that the API returns 403 until the 1st of next month (UTC). 1 credit = 1 minute, with a 10-credit minimum per API project. — [OpusClip API Limitations](https://help.opus.pro/api-reference/limitation)
- Plan access is contested: "Pro (beta) + Business" per some sources, Business/custom only per others. — [eesel](https://www.eesel.ai/blog/opusclip-pricing); [usagepricing](https://www.usagepricing.com/blueprint/opus-clip)
- The API accepts the same sources as the web app plus any public S3 MP4 link. — [OpusClip Help: import sources](https://help.opus.pro/docs/article/what-import-sources-does-opusclip-support)
- One low-quality guide shows a `/v2/clips` endpoint. Unverified; prefer the official `clip-projects` endpoint. — [ssemble](https://www.ssemble.com/blog/opus-clip-pricing-2026)

**Vizard API**
- Docs are at docs.vizard.ai. Submit a long video with `videoUrl`, `videoType` (Twitch = 9) and `preferLength`. Output clips are retrieved by polling or callback. A short-video editing endpoint is also available. An official GitHub "vizard-api-skills" repo provides agent integration specs. — [Vizard Submit](https://docs.vizard.ai/reference/submit); [Retrieve clips](https://docs.vizard.ai/docs/retrieve-video-clips); [Short video editing](https://docs.vizard.ai/docs/submit-a-short-video-for-editing); [GitHub vizardai/vizard-api-skills](https://github.com/vizardai/vizard-api-skills)
- Rate limit (official): `/project/create` is limited to 3 requests per minute and 20 per hour, with custom limits on request. A third-party site cites per-plan limits (Free 1/min, Creator 3/min, Business 10/min). — [Vizard Rate Limit](https://docs.vizard.ai/docs/rate-limit); [aitoolcurator](https://www.aitoolcurator.com/ai-tools/content-creation/vizard-ai/)
- Pricing: included with paid Creator and Business plans (no separate API subscription) and drawn from plan credits. `clip_v2` costs 1.25x the v1 rate. — [cybernaira](https://cybernaira.com/ai-video-clipping-apis/)

**Klap API**
- `POST /tasks/video-to-shorts` with a video URL (public YouTube URLs accepted directly), then poll the task, then export. Pay per operation: $0.44 per input video, $0.32 per short, $0.48 per export. — [Klap API](https://klap.app/api); [itechguides](https://www.itechguides.com/best-ai-video-clipping-api-klap-pricing-and-code/); [bloggingspark](https://www.bloggingspark.com/klap-api-vs-opusclip-api/)

**Submagic API**
- Docs are at docs.submagic.co. Magic Clips is `POST https://api.submagic.co/v1/projects/magic-clips` and accepts a YouTube URL. It needs an API key plus a Magic Clips subscription and is limited to 500 requests per hour. — [Submagic API Intro](https://docs.submagic.co/introduction); [Create Magic Clips](https://docs.submagic.co/api-reference/magic-clips)
- API minutes: Starter and Pro include 10 per month, Business ($69/month) includes 100. Extra packs: 250 minutes for $57, 500 for $75, 1,000 for $150, 10,000 for $1,000 (about $0.23 down to $0.10 per minute). Partial minutes round up. — [cutsnap Submagic pricing](https://cutsnap.ai/blog/submagic-pricing-2026); [zapcap (competitor)](https://zapcap.ai/api/alternatives/submagic/)

**Reap API**
- Base URL is `https://public.reap.video/api/v1/automation/` with a Bearer key. Endpoints include create-clips, create-reframe and get-project-status. Rate limits are 60 reads, 30 writes and 10 project creations per minute. Reframe is paid-only. There is also an MCP server. — [Reap API Intro](https://docs.reap.video/api-reference/1_introduction); [Create Reframe](https://docs.reap.video/api-reference/create-reframe); [Reap MCP docs](https://docs.reap.video/api-reference/mcp)

**Captions / Mirage API**
- Gated beta as of August 2026, by application. Host is `api.mirage.app` with `x-api-key` auth. The official API pricing page lists Avatar X at $0.15 per second of output, billed in 6-second increments (page modified 13 August 2026). Third parties cite $0.45 per input minute, a conflict. Focused on avatars, dubbing and captions; I found no evidence of a URL-to-clips endpoint. — [Captions API pricing](https://captions.ai/help/docs/api/pricing); [autohustle](https://autohustle.me/blog/captions-mirage-pricing-2026); [videoai.me](https://videoai.me/mcp-servers/captions)

**Others**
- MagicAI ("Viral Clips") documents a similar API. — [MagicAI docs](https://docs.magicproject.ai/viral-clips/)
- No API was found for Eklipse, StreamLadder, Spikes Studio, quso, 2short, Choppity or Munch. — (absence in searches; see Gaps)

### Inferences
- For a "paste URL, get rendered clips" integration: Vizard (cheapest if you're already on a $29 plan, but only 20 submissions per hour), OpusClip (broadest sources including Kick and Rumble, but capped at 900 minutes a month on Pro and Max) and Klap (no quota cap; at $0.44 + $0.32 × N + $0.48 × exports, 10 exported shorts from one video costs about $8.24) are the realistic choices. Reap is the most agent-friendly (MCP).
- Twitch: OpusClip and Vizard both take Twitch links. Because they meter by duration, a full VOD is technically possible (OpusClip up to 10 hours) but expensive. Klap and Submagic docs only mention YouTube URLs.

### Gaps
- I found no explicit documentation saying whether Twitch *clip* URLs (clips.twitch.tv) vs *VOD* URLs (twitch.tv/videos/…) are supported for OpusClip or Vizard. Behavior with subscriber-only or expired VODs is also undocumented in the results.
- Klap and Submagic support for non-YouTube URLs (Twitch, Kick, Rumble) was not confirmed.
- Kick and Rumble support via the Vizard API was not found.

## Q3. Which tools target Twitch streamers and use chat activity as a signal?

### Takeaway
Eklipse is the main incumbent. It processes full Twitch/Kick VODs after the stream, and its own pages claim chat-spike detection since a July 2026 engine update, though competitors dispute this. Spikes Studio auto-clips post-stream, but its "spike" is a keyword mods type manually. StreamLadder is mainly an editor/reformatter, with AI clipping (ClipGPT) on paid tiers. Powder has shut down. Newer entrants (ClipMe, Klypra, Nexus Clips) market automatic chat-velocity scoring and live clipping, but those claims are self-published.

### Cited Findings
- **Eklipse**: its AI Highlights page says a July 2026 engine update added chat spikes and reaction moments to game events, on-screen markers and audio peaks, scored across the full VOD. — [Eklipse AI Highlights](https://eklipse.gg/features/ai-highlights/); [Eklipse Twitch clip maker](https://eklipse.gg/features/twitch-clip-maker/)
- Competitor ClipMe says Eklipse reads game events across 1,000+ titles and does not read chat. ViddyFlow rates Eklipse's chat analysis as "Limited". — [ClipMe vs Eklipse](https://clipme.com/vs/eklipse); [viddyflow](https://viddyflow.com/blog/best-ai-tools-to-turn-twitch-streams-into-clips-2026/)
- Eklipse says it fully supports Kick VODs and processes each session automatically when it ends. — [Eklipse Kick blog](https://blog.eklipse.gg/streaming-tips/how-to-clip-on-kick-2.html)
- Eklipse pricing: Premium is $24.99/month or $179.99/year (about $15/month). A $112.99 six-month option is also reported. A $9.99/month figure from July 2026 is unconfirmed. Free tier: sources say it has been "fully paid since June 2026", or "3 AI highlights total since June 1, 2026", or that the free plan only previews clips and export requires Premium. — [Eklipse Twitch clip maker](https://eklipse.gg/features/twitch-clip-maker/); [clipme](https://clipme.com/best-twitch-clipper); [agent-finder](https://agent-finder.co/reviews/eklipse)
- **Spikes Studio**: connects to Twitch and auto-clips after the stream ends. Its chat "spike" is a keyword moderators enter by hand, not automatic velocity scoring. The free tier has a watermark and is capped at 720p. PRO+ is $32.99/month ($14.09/month billed yearly) for 300 minutes a month (single source). — [clipme](https://clipme.com/best-twitch-clipper); [stealwhatworks](https://stealwhatworks.com/blogs/news/short-form-video-pricing)
- **StreamLadder**: a clip editor (facecam/gameplay vertical layouts). Two sources say it does not find highlights in VODs; others say AI VOD clipping is ClipGPT on paid tiers. App Store pricing: Starter $14.99/month, Creator $26.99, Pro $38.99, "Gold + ClipGPT" $26.99. A cheaper Silver tier ($8.28 to $8.99/month) also appears. Free: uploads up to 200 MB, 720p/30fps export. — [App Store](https://apps.apple.com/us/app/streamladder/id6760137802); [vidpros](https://vidpros.com/streamladder-review-2026/); [nexusclips](https://nexusclips.com/blog/best-clipping-software-for-streamers-2026); [makeaivideo](https://makeaivideo.ai/blog/best-twitch-clip-makers-2026)
- **Powder.gg**: shut down. Its farewell note says the app is no longer updated and subscriptions were cancelled. The date varies by source (late 2024, 2025 or July 2026). It was a Windows-only desktop app with Free and Pro tiers. — [clipme Powder](https://clipme.com/powder-alternative); [fragcut](https://fragcut.io/alternatives/powder-gg); [Eklipse vs Powder](https://eklipse.gg/compare/eklipse-vs-powder/)
- **Medal.tv**: in-game recorder with AI "ICYMI" auto-clip of key moments since 2020 (15-second cooldown). Planned "smart trimming" builds on its General Intuition partnership. Game-event based, not chat; for PC gameplay, not for clipping VODs from links. — [Medal on X](https://x.com/Medal_TV/status/1288584748818980865); [Medal blog](https://medal.tv/blog/posts/medal-x-general-intuition-how-clips-and-gameplay-actions-create-spatial-intelligence)
- **ClipMe** (new): says it turns one Kick, Twitch or YouTube stream into 50–100 captioned clips scored by a multi-signal model including chat velocity, and cuts clips live mid-broadcast (vendor self-assessment). — [clipme Twitch clipper](https://clipme.com/twitch-clipper); [clipme gaming](https://clipme.com/best-ai-clipper-for-gaming)
- **Klypra** (new): clips live streams, including other people's, from chat activity. Free: 1 day every 7 days, 4 hours of monitoring, 5 clips (vendor blog). — [klypra](https://klypra.app/blog/best-ai-tool-to-clip-twitch-streams)
- **Nexus Clips** (new): detects highlights in live and full streams based on prompts. No confirmed chat-velocity use. — [nexusclips](https://nexusclips.com/blog/best-clipping-software-for-streamers-2026); [CB Insights](https://www.cbinsights.com/company/nexus-clips)
- **Other VOD-focused tools**: ViddyFlow (paste a full Twitch VOD, get a highlight reel plus shorts) and Highlight Hunter by FrostyTools (tokens from about $0.25 per VOD hour). — [viddyflow](https://viddyflow.com/blog/best-ai-tools-to-turn-twitch-streams-into-clips-2026/); [frostytools](https://frostytools.com/blog/how-to-turn-twitch-vods-into-clips-without-editing/)
- **Mirage "Clips in Captions"** markets gaming support but no chat signal. — [Mirage on X](https://x.com/trymirage/status/2100639477173760510)

### Inferences
- Chat-velocity spike detection is a differentiator mostly claimed by small 2026 entrants (ClipMe, Klypra) and recently by Eklipse. It is not a feature of OpusClip, Vizard, Klap or Submagic, which judge moments only from audio, video and transcript. This leaves room for a tool that fuses Twitch chat logs (fetched via the VOD's chat replay) with transcript/audio scoring.
- Almost all claims about rivals' chat features come from competitors' marketing pages, so independent verification (e.g., a test VOD with a known chat spike) would be needed.

### Gaps
- No independent benchmark of chat-signal accuracy for any tool was found.
- Sizzle / Clip.studio: no 2026 information surfaced. Status unknown and possibly defunct.
- Whether Eklipse or Spikes accept arbitrary pasted VOD links (vs only a connected own channel) was not confirmed.

## Q4. Current (Nov 2026) pricing tiers and free-tier limits, summary; shutdowns and pivots

### Takeaway
Entry paid tiers cluster at $15–$29/month (about $10–$15/month billed yearly). Free tiers are mostly 30–75 source minutes a month with a watermark and 720p, except 2short (no watermark) and Klap (one free video). Status changes to flag: Powder shut down, Munch pivoted to Munch Studio (no standalone clipper), vidyo.ai became quso.ai (January 2025), Captions became Mirage (September 2025), and Eklipse removed or cut its free tier around June 2026.

### Cited Findings
| Tool | Free tier | Paid tiers (monthly / yearly-equivalent) | Unit | Source |
|---|---|---|---|---|
| OpusClip | 60 credits (monthly vs one-time disputed), watermark, clips kept 3 days, no editor | Starter $15 (150 credits, no watermark, 9:16, auto-post; monthly only); Pro $29 / $14.50 (300 credits, 3 aspect ratios, 2 seats, scheduler, API beta); Business custom | 1 credit = 1 source minute | [lumiclip](https://www.lumiclip.ai/blog/opus-clip-pricing); [eesel](https://www.eesel.ai/blog/opusclip-pricing); [usagepricing](https://www.usagepricing.com/blueprint/opus-clip) |
| Vizard | 60 min/month, 720p, watermark, 3-day expiry | Creator $29 / $14.50; Business $39 / $19.50 | 1 credit = 1 minute | [layer3labs](https://www.layer3labs.io/guides/vizard-ai-pricing) |
| Klap | 1 free video | $29 / $79 / $189 (100 / 300 / 1,000 clips); minutes-based per one source | clips (or minutes) | [Klap pricing](https://klap.app/pricing); [valmera](https://valmera.io/blog/klap-review) |
| Submagic | 3 watermarked videos | $19 / $39 / $69 ($12 / $23 / $41 yearly) for 15 / 40 / 100 videos; Magic Clips add-on about $19 | videos | [funova](https://funova.ai/en/submagic-review/) |
| Captions/Mirage | — | Pro about $9.99; Max $24.99 (500 credits); Scale $69.99–$279.99 (iOS prices) | credits | [cutsnap](https://cutsnap.ai/blog/submagic-vs-captions-ai) |
| quso.ai | 75 credits/month | Lite $29 / $19; Essential $39 / $26; Growth $49 / $33 | about 1 minute | [shortzly](https://shortzly.com/blog/vidyo-ai-alternative) |
| 2short.ai | 30 min/month, no watermark | $9.90 (5 h), $19.90 (15 h), $49.90 (50 h) | hours analyzed | [cut.pro](https://cut.pro/en/blog/cheap-ai-clipping-tools-2026) |
| Reap | 1 h, 720p | Creator $24 / $9.99 (10 h; 600 credits/month) | credits | [cut.pro](https://cut.pro/en/blog/cheap-ai-clipping-tools-2026); [Reap API](https://docs.reap.video/api-reference/1_introduction) |
| Choppity | ? | $20 / $14 (3 h) or $24 / $16.80 (1 h), conflicting | hours | [cut.pro](https://cut.pro/en/blog/cheap-ai-clipping-tools-2026) |
| Eklipse | none, or 3 highlights, or preview only (since June 2026) | Premium $24.99 / $179.99 per year | — | [Eklipse](https://eklipse.gg/features/twitch-clip-maker/) |
| Spikes Studio | watermark, 720p | PRO+ $32.99 / $14.09 (300 min) | minutes | [stealwhatworks](https://stealwhatworks.com/blogs/news/short-form-video-pricing) |
| StreamLadder | 200 MB, 720p/30fps | Starter $14.99; Creator / Gold+ClipGPT $26.99; Pro $38.99 | — | [App Store](https://apps.apple.com/us/app/streamladder/id6760137802) |
| Kapwing | watermark, short exports, 10 AI credits | Pro $24 / $16; Business $64 / $50 | AI credits | [fluxnote](https://fluxnote.io/guides/kapwing-pricing-2026) |
| VEED | 10 min clipping | about $12.25/editor/month (yearly) | — | [reap benchmark](https://reap.video/reports/state-of-top-ai-video-clipping-tools-2026) |
| Munch Studio | none (7-day trial) | — (pivoted) | — | [kompozy](https://kompozy.io/reviews/munch) |
| Powder | shut down | — | — | [clipme](https://clipme.com/powder-alternative) |

- Submagic is running Black Friday 2026 promotions, so prices may be temporarily discounted around the time of this note. — [toolsurf](https://www.toolsurf.com/submagic-black-friday-2026-2026/)

### Inferences
- The cost per hour of source video is about $6/hour on OpusClip Starter ($15 / 150 minutes), $5.80/hour on OpusClip Pro (monthly), about $3.6–6/hour on quso, and about $1/hour on 2short Premium. VOD-oriented tools like Highlight Hunter (about $0.25/hour) are an order of magnitude cheaper, so for multi-hour Twitch VODs, minute-metered general clippers are a poor fit on cost.

### Gaps
- None of the vendor pricing pages could be fetched directly. All numbers are from search-surfaced third-party reviews (many by competing tools) and should be re-verified.
- Riverside, Descript, CapCut, Clipchamp and Medal pricing for clip features was not retrieved.
