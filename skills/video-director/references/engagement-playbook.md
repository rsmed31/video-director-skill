# Engagement playbook (short-form first, applies broadly)

Researched 2026-10-16. Only a few points are confirmed by Instagram itself (skip rate and the retention chart, watch time including replays, sends/saves/likes as top signals, the 3-minute recommendation limit, reach penalties for watermarks and unoriginal content). Everything else is vendor or agency practice. Treat the numbers as **starting defaults**: `director.yaml` rules carry confidence values, and user feedback and real Insights override them. Anchors (`#hook` etc.) are cited by rule evidence.

## hook
- Instagram reports **skip rate** = % of views that leave in the first 3 s, plus a per-Reel retention chart. Watch time counts replays.
- Cut the settle-in. Open on the strongest claim, result, question or symptom, within 2 s.
- **Text hook on frame 0:** 4–7 words, high contrast, placed in `hook_text_band` (~20–25% from the top). Complement the spoken line, don't transcribe it. Open a loop that pays off later.
- First visual change by ~2.5–3 s: punch-in, cutaway or graphic.
- A spoken question hook ("have you ever heard of X?") works best when the answer *lands visually* the moment it is spoken.

## pacing
- Remove silences longer than ~0.4 s, fillers, false starts and retakes. A typical tightening is 64 s → 48 s with no content lost.
- Shots run 1.5–6 s. A shot may hold 8–10 s if something is developing (a graphic building, a drift).
- Change something every 3–6 s, densest in the first 15 s. Sources disagree (3–7 s vs 15–60 s), so the profile's `max_static_s` decides.
- **Punch-ins:**
  - 108–120% on key lines; 130–150% for an emphasis close-up. Alternate wide and tight.
  - About 3–4 per 30 s. One edit cut 11 zooms in 30 s down to 3 and got better.
  - Add a constant slow drift (100→105%) so the frame never fully rests.
- **Over-editing backfires.** If every sentence gets a zoom and a whoosh, the effect becomes the pattern. Older and professional audiences tolerate less.
- **Length:** 15–30 s for one idea; 30–60 s for an explanation; under 3 min for recommendation eligibility.

## motion
- **Current:** hard and jump cuts as the default; speed ramps; beat-synced cuts; match cuts or whip pans only when motivated by on-screen motion; zoom-through transitions into a graphic.
- **Dated when overused:** stock light leaks, flash or glitch on every cut, preset 3D wipes. Keep these to 1–2 per minute (`caps`).
- **Structure graphics** (step chips "1/3", checklists, numbered lists, progress bar) help comprehension. Keep the progress bar thin and inside the safe zone.
- **Data and diagrams:** build them up (bars grow, counters tick, arrows draw, labels pop), hold ≥1.5–2 s readable, then **move the camera into the key element**, then return to the speaker.
- **B-roll stills:** never static. Ken Burns, parallax layers, or an image-to-video clip.

## captions
- Word-synced captions are the baseline now, not a differentiator.
- Chunk 2–4 words (6 max), 1–2 lines, heavy sans, light fill with a dark stroke or shadow, ~64–78 px on a 1080-wide canvas.
- Highlight ≤1 word in 10 (accent color, slight scale pop). Emoji rarely, only on keywords.
- Place in `caption_band` (Reels ≈ y 1080–1250, never lower than ~1250).
- **RTL scripts (Arabic, Hebrew, Persian):**
  - Use a bold Arabic sans (Cairo, Tajawal, Noto Kufi Arabic, IBM Plex Sans Arabic), embedded with @font-face.
  - Set `dir="rtl"`; isolate Latin terms (`unicode-bidi: isolate`).
  - Give extra line height for the dots and diacritics.
  - Word-by-word highlighting must follow RTL order.
- Native script vs a romanised spelling depends on the audience; ask the client, or A/B test if unsure.

## safe-zones
- No official organic spec. Use the platform block in `director.yaml`. Reels (conservative):
  - top 270 px, bottom 670 px, sides 65 px clear;
  - the right rail (~x > 850 for y > 1150) also clear.
- When the subject fills the safe area, change layout instead of overlapping:
  - shrink the speaker into a split (speaker top, visual bottom-safe);
  - full-frame cutaway;
  - a small PiP card above the caption band, away from the face.
- **Cover:** key text and face inside the central 1080×1440. Choose the cover frame before posting; it can't be changed afterwards.

## sound
- **Three layers:** clean voice; music bed −18…−24 dB under the voice (a bit higher in gaps), ducked during speech; SFX.
- **SFX mapping:**
  - whoosh (0.3–0.5 s) on cuts and entries;
  - **riser → hit** on section changes, with the riser ending exactly on the cut frame;
  - pop or click on text;
  - chime or ding on checks and correct answers;
  - typing on typed text.
- Vary samples, keep SFX out of the voice band, check on a phone speaker. SFX volume about 0.25–0.45 relative.
- Beat-sync graphic entries when a music bed has a clear grid.
- Trending audio matters less for voice-led education. Licensed or royalty-free beds are safe.

## broll
- Treat every concrete noun or action in the script (object, tool, action, product, place) as a b-roll candidate.
- Use a cutaway every 8–15 s, 2–4 s long. Mix stills (animated) with 2–5 s AI clips. Cut on phrase boundaries; the voice keeps running.
- Layout options: full-frame cutaway; split (speaker top / visual bottom); PiP card. Rotate between them.
- **AI disclosure:** realistic generated scenes, especially of people, get Instagram's "AI info" label. Don't strip C2PA metadata. Never fake the speaker or present a generated person as real.

## ending
- Loop: the last line or frame flows back into the opening (completes a sentence, or matches visually). Replays add watch time.
- CTA in the last 2–4 s, both spoken and on screen:
  - **save** for reference-style content ("save this checklist");
  - **send** for relatable content ("send this to someone who…").
  - Sends reach non-followers the most.
- Originality: no other apps' watermarks, no reposted content.

## export
- **Video:** 1080×1920 H.264 High, yuv420p, 30 fps (60 only if the source is 60), VBR ~10 Mbps (cap 25), `+faststart`.
- **Audio:** AAC 48 kHz, 192 kbps.
- **Loudness:** −14 LUFS integrated, −1 dBTP true peak. Instagram's own normalization is undocumented; some sources suggest −10 to −12. Adjust if the user reports quiet audio.

## Sources
socialmediatoday.com/news/instagram-adds-retention-insights-reels · socialsamosa.com (skip rate) · metricool.com/instagram-reel-analytics · news.inman.com 2025-03 (Mosseri signals) · async.com/blog/how-to-edit-instagram-reels · faceless.so/blog/retention-first-editing · teleprompter.com/blog/hooks-for-instagram-reels · hopperhq.com/blog/instagram-reel-size · firstpier.com/resources/instagram-ad-safe-zones · blitzcutai.com (caption size/style 2026) · capcut.com (transition trends; bitrate) · soundstripe.com (overused transitions) · openclip.app (ducking; LUFS) · sounddesign.irpr.agency · buffer.com/resources/instagram-reels-length · project-aeon.com (1,500-video study) · reap.video/blog/ai-video-disclosure
