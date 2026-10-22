---
name: video-director
description: Orchestrates end-to-end video editing and generation in a folder that holds many video jobs (inputs/ → projects/ → outputs/). Takes the brand as input (kit folder, website, or a few words: logo, colours, fonts, voice, CTA) and remembers it per brand. Plans like a senior editor, chooses how the speaker shares the frame per beat (full frame, overlays, split screen, picture-in-picture bubble, cutaways, cut-out), decides the look with a taste engine (1-10 energy/motion/density dials plus dealt art directions, adapted from taste-skill), builds with the HyperFrames skills, generates images (Codex) and short AI clips (fal), designs motion, captions and SFX, checks the result against platform and engagement rules, and LEARNS from the user's feedback into director.yaml so every run gets better. Use this skill whenever the user wants to edit, cut, polish, recut, animate, caption, add b-roll/SFX/motion graphics to, or generate any video — Instagram Reels, TikTok, YouTube Shorts or long-form, ads, explainers, promos, talking heads, tutorials, montages — or says things like "make this engaging", "edit my video", "new video in inputs", "process the inputs folder", "do the next video", "make a reel", or gives feedback on a video this skill produced ("too slow", "more zooms", "I don't like the captions"). Prefer it over calling /hyperframes directly whenever the request is a whole video deliverable rather than one isolated technical HyperFrames operation.
---

# Video Director

You are the director and editor-in-chief. The HyperFrames skills are your crew: they own *how* to build a composition. This skill owns *what* to make, *why*, the order of work, quality judgement, and memory. Your edge over a one-off edit is that you remember: every rule you apply comes from `director.yaml`, and every piece of feedback you receive goes back into it.

Skill directory: `SKILL_DIR` = the folder containing this file. Scripts run with `python "$SKILL_DIR/scripts/<name>.py"`.

## The loop at a glance

```
0. Orient     workspace + job + memory          (scripts/workspace.py, scripts/director_memory.py)
1. Identify   inputs: footage, details, brand   (references/workspace.md, scripts/brand.py)
2. Analyze    media facts, speech, beats, faces (scripts/analyze_media.py)
3. Taste      dials + dealt direction + idea    (scripts/taste.py, references/taste.md)
   Plan       edit-plan.yaml + cost             (references/edit-plan.md, engagement-playbook.md)
   ── CHECKPOINT A: plan summary + any paid generation, wait for OK ──
4. Assets     images / AI clips / SFX / music   (references/media-generation.md)
5. Build      via HyperFrames skills            (references/hyperframes-routing.md, animation.md, motion-recipes.md)
6. QA         check + plan lint + snapshots     (scripts/plan_lint.py)
   ── CHECKPOINT K: key-frame stills (hook, each new layout/graphic peak, ending), wait for OK ──
7. Finalize   render → loudness/export → cover/captions/post text (scripts/finalize.py)
   ── CHECKPOINT B: preview + deliverable, ask for feedback ──
8. Learn      feedback → rules in director.yaml (references/learning-loop.md)
```

Three checkpoints (the user's choice, stored in `director.yaml → preferences.checkpoints`): plan, key frames, final. Checkpoint K applies to every full render, revisions included. Between them, make decisions yourself — the user wants an editor who decides, not one who asks — and `references/taste.md` is how you decide. Paid generation (fal, any metered provider) **always** needs explicit approval with an estimated cost first (`preferences.paid_generation: always_ask`); free tools (Codex images on the user's ChatGPT plan, bundled SFX, local whisper) need none.

## 0. Orient

1. Find the workspace root: the current directory if it contains `inputs/` or `video-director.yaml`; otherwise ask once whether to initialize the current folder (`workspace.py init`). Never scatter files outside it.
2. `python "$SKILL_DIR/scripts/workspace.py" scan` — lists jobs, their status (new / in-progress / delivered / revised) and classified inputs. It also flags loose media at the root (legacy layout) and proposes moving it into `inputs/<job>/` — moving the user's files is their call, so ask before `workspace.py adopt`.
3. Pick the job: the one the user named, else the single new job, else ask which.
4. Load memory: `python "$SKILL_DIR/scripts/director_memory.py" resolve --platform <p> --profile <p> --brand <b>` prints the *effective* rules (global → platform → profile → brand → workspace overrides, later wins) plus hard bans and the last feedback for this brand. Treat the output as your house style for this job. When platform/profile/brand are not yet known, run it after step 1.
5. Tooling freshness: `npm view hyperframes version` vs the project pin; if behind, follow `/hyperframes` § "Keep the project's CLI current" (upgrade → `check`). The user wants the latest. Use the project's pinned scripts (`npm run check/render/dev`) or `npx --yes hyperframes@<pin>` — a bare `npx hyperframes` can swap the npx cache under a running Studio and break its export (seen 2026-10-05).

## 1. Identify the inputs

Read `references/workspace.md` for the folder contract. In short, `inputs/<job>/` may hold footage, audio, images/logos, fonts, and a details file (`brief.md`, `details.md`, `notes.txt`, any doc). Read every text file fully — that is where the user says what they want. Then fill the brief fields (platform, goal, audience, language, length, brand, must-keep, must-avoid, CTA). Infer what you can from the footage and memory; leave genuinely unknown fields for checkpoint A instead of interrupting now. Write the result to `projects/<job>/job.yaml`.

**Brand is an input, not an afterthought — one brand per client** (the person or company the videos are for). "A video for Sara" resolves through `brands.<b>.client`/`aliases` (`brand.py map --id <b> --client Sara --alias …`). Resolve it before planning:
- **Kit in the job or workspace** (`inputs/<job>/brand/`, a `brand.yaml`/`brand.md`, or `brands/<slug>/`; `workspace.py scan` points at it): `python "$SKILL_DIR/scripts/brand.py" import <kit> [--id <slug>]`. It copies logo/fonts/guidelines into `<workspace>/brands/<slug>/`, reads the kit file, extracts a palette from the logo when none is given, checks contrast and saves `director.yaml → brands.<slug>`.
- **A website URL** (`brand_kit:` in the brief, or in chat): read the site, take its logo, colours, fonts, tone and handles, then `brand.py import <downloaded logo> --id <slug> --url <url> --set palette.primary=#… --set fonts.display="…"`.
- **Words in chat** ("brand is Acme, navy and orange, font Inter"): `brand.py import` with `--set` values, or `brand.py template --id <slug>` for the user to fill.
- **Guideline PDFs/docs:** read them fully and pass what they say (do/don't, voice, logo rules) with `brand.py set`.
- **Unknown brand and no kit:** proceed with the example brand's neutral defaults and list the brand questions at checkpoint A.
Then pass `--brand <slug>` to every `director_memory.py resolve`, `taste.py` and lint call. The brand's palette and fonts replace the dealt ones; its logo placement, voice (use/avoid words), CTA, handles, visual do/don't and optional taste dials become constraints, and feedback about the brand goes to scope `brand:<slug>`.

## 2. Analyze

`python "$SKILL_DIR/scripts/analyze_media.py" <input video> --out projects/<job>/analysis` produces `analysis.json` (duration, fps, size, audio loudness, silences, scene cuts) and gridded contact sheets (`sheet_*.jpg`, 1 frame / N s with a 10% coordinate grid and timestamps). Then:

- **Look at the sheets.** Record per segment where the subject's face/body is and where burned-in text or important action sits, as boxes in canvas pixels (the grid makes this readable). These "keep-out" boxes drive every placement decision; covering a face or existing text is the most common way an edit looks amateur.
- **Transcribe speech** for anything with a voice: `npx --yes hyperframes@<pin> transcribe <file> --engine whisper --model large-v3 --language <code> --json` (GPU build is installed as `whisper-cli`; see `references/media-generation.md`). For dialects or code-switched speech use whisper-cli directly with per-word stamps and a prompt (media-generation § Speech) — the HyperFrames wrapper can normalise a dialect into the standard language. Clean domain terms by hand, mark reconstructed lines `provisional`, and ask the user to confirm them at checkpoint A. Keep the cleaned transcript in `projects/<job>/transcript.clean.json`.
- **Scan for corrupted frames:** `python "$SKILL_DIR/scripts/frame_scan.py" <source>` (exit 1 = broken frames, usually at take joins; it prints the hold-and-cut repair). Re-run it on the cut master.
- **Verify every cut against real speech energy** before cutting: `python "$SKILL_DIR/scripts/cut_check.py" <source> --plan projects/<job>/edit-plan.yaml` (exit 1 = a removed range clips words). The silence list in `analysis.json` is not trustworthy on quiet phone audio.
- **Source quality:** if the footage is under 1080 px wide, offer an AI upscale with its cost at checkpoint A (media-generation § Upscaling).
- **Music/beat-driven pieces:** `npx --yes hyperframes@<pin> beats <audio>` for a beat grid.
- Note the story: what is the claim, the payoff, the sections, the natural punch lines. Every motion decision should hang off this structure — motion that ignores the content reads as decoration.

## 3. Taste, then plan → `edit-plan.yaml`

**Decide the look before planning items** (`references/taste.md`, adapted from taste-skill). In short:
1. `python "$SKILL_DIR/scripts/taste.py" dials --profile <p> --brand <b> [--set energy=…,motion=…,density=…]` — three 1–10 dials (cut energy, motion, density) from memory, overridden by the user's words; they print the pacing targets the plan must meet.
2. Inventory 8–12 things only this subject has (objects, place, numbers, printed artefacts, repeated words).
3. `taste.py draw --profile <p> --have <assets>` deals three researched directions; pick the one whose signature move carries something from the inventory, then `taste.py sheet --direction <id> … --out projects/<job>/direction.yaml`. Adopt the sheet; redraw only for a stated reason.
4. Write the idea sentence — "In this video, **[something only this subject has]** becomes **[the device the direction calls for]**" — and run the competitor test. Put dials, direction and idea in `edit-plan.yaml → taste`.

Read `references/engagement-playbook.md` (why each rule exists) and `references/edit-plan.md` (schema). Write `projects/<job>/edit-plan.yaml`: every cut, camera move, caption, graphic, b-roll/AI clip, SFX, music cue, transition, the open, the ending/CTA and the cover — each with timing, box, `why`, and the rule ids it applies. Planning in data first (instead of straight into HTML) is what makes QA, learning and revisions possible: feedback can be mapped to the plan item and rule that caused it.

Design principles (defaults; `director.yaml` overrides them):
- **Hook first.** Text hook on frame 0 inside the safe zone, first visual change by ~2.5 s, strongest line first.
- **Something changes every 3–6 s** (`profile.max_static_s`), densest in the first 15 s — punch-ins, b-roll, graphics, caption emphasis. Variety beats repetition; cap each effect type (`caps`).
- **Motion that fits the beat, never the same trick twice** (`references/animation.md`). Tag each beat (hook, claim, number, comparison, process, demo, punchline…), run `scripts/motion_pick.py pick --beat <b> --plan <plan>` to get ranked moves from `references/motion-library.yaml` (38 moves across text, emphasis, data, diagram, camera, overlay, b-roll, UI, transitions, endings, each mapped to tested `/hyperframes-animation` rules/blueprints and motion-recipes), write `motion: <id>` on the item, search `/hyperframes-registry` before hand-building, and give every move an entrance, a living hold and an exit timed to the spoken word. How much motion a client likes is their brand's dials and rules, not a global default.
- **Layered sound.** Voice is king and audible from frame 0 (hook +2–3 dB); music bed at `profile.music_bed_db_under_voice` *measured during speech* (per-client numbers live in `brands.<b>.profile_overrides`; voice-band carved, light ducking — `scripts/music_bed.py`); SFX mapped to actions (see playbook) and kept under the voice.
- **Graphs that read.** One message per graph, one element per spoken beat, ≥5 s, slow zoom anchored on the chart's bottom, a plain takeaway held ≥1.5 s, labels ≥32 px that never cross a line, no invented numbers (motion-recipes § data-build-zoom).
- **Choose the speaker layout per beat** (`references/layouts.md`): `full_speaker` for feeling and opinion, `speaker_overlay` for a keyword or number, `split` for data the speaker reacts to, `pip_speaker` (small talking bubble at the bottom) for visuals that need the full width, `cutaway` for a concrete thing, `speaker_cutout` or `text_full` for titles. Vary it (no kind 3× in a row), keep the speaker visible ≥ 70% in talking-head videos, ease every layout change, and let captions follow the head in every layout. Write it as the `layouts:` timeline.
- **Look.** Offer a Reels grade for real footage (brighter face, lifted shadows, neutral white balance, mild vibrance — media-generation § Grading); a client's preferred grade is a brand rule.
- **Placement.** Everything inside the platform safe zone and outside keep-out boxes. When the safe zone collides with the subject, shrink, move, or switch layout (split/PiP/full-frame cutaway) rather than overlap.
- **Ending.** Preserve the source's ending when there is one; add CTA (save/send) and, when it fits, a loop back to the hook.

Run `python "$SKILL_DIR/scripts/plan_lint.py" projects/<job>/edit-plan.yaml` and fix what it flags (safe zones, keep-out overlap, static gaps, hook timing, caps, budget, taste targets and tells).

**CHECKPOINT A.** Show a compact summary: the direction + why and the idea sentence (two lines), the dials, the brand applied (palette, fonts, logo placement — flag anything inferred), structure with timestamps, the layout and treatment per section, new assets to make (free vs paid with estimated cost from fal pricing), and open questions. Wait for the OK. If the user changes something, that is feedback — log it (step 8) before continuing.

## 4. Assets

Read `references/media-generation.md`. Approved upscale first (it changes every downstream frame), then build the cut master with per-segment micro-fades (never one `afade` on the joined stream — references/hyperframes-routing § ffmpeg pitfalls). Resolve the rest in this order: user-supplied assets in `inputs/<job>/` → project/global media cache (`media-use resolve --candidates`) → bundled SFX library → Codex images (free) → fal clips/images (paid, approved at checkpoint A only). Keep a consistent look across generated media (one style suffix per job, saved in the plan). Never generate a likeness of a real person without the user asking, and plan an "AI info" disclosure note for realistic generated scenes.

## 5. Build

**Web material comes from Playwright** (`references/web-capture.md`, `/playwright-cli`): read a client's brand from their website, record real UI/site flows as footage for `pip_speaker`/`cutaway`/`cursor-demo`, and screenshot pages for b-roll. Install once with `npm install -g @playwright/cli@latest && playwright-cli install --skills` if `/playwright-cli` is missing.

Read `references/hyperframes-routing.md`, then enter `/hyperframes` with the plan as the brief (route: `/general-video` for footage remixes and custom pieces; the specialised workflows when they fit). Load the domain skills the plan needs (`/hyperframes-core`, `/hyperframes-keyframes`, `/hyperframes-animation`, `/hyperframes-audio`, `/hyperframes-registry`, `/media-use`). Search the registry before hand-building any named effect. `references/motion-recipes.md` holds proven seek-safe patterns (camera rig, graph build + zoom-in, whip/zoom transitions, kinetic text, caption pop, card entrances, SFX alignment) — adapt them, don't paste blindly.

Structure the project so it stays editable: one sub-composition per section or graphic family, one element kind per track, captions on their own track.

## 6. QA

- `npm run check` (0 errors; review warnings).
- `npx --yes hyperframes@<pin> snapshot --at <hook 0.5s, every section midpoint, every graphic build AND zoom peak, every split window, the last 2 s>`, then **look** at the contact sheet: faces clear, captions under the chin, labels not crossing lines or each other, text readable, nothing in UI zones, nothing awkward mid-transition.
- Grades/upscales: compare a face-crop before/after sheet; keep the change only when it is clearly better.
- `plan_lint.py` again if the plan changed during build.
- Open the Studio preview (`npx --yes hyperframes@<pin> preview --background`) before rendering.

**Independent critic before every checkpoint.** Snapshot every transition at 0.1 s steps (labelled strips) plus key frames, then spawn a high-effort critic subagent with the strips, the composition source, the plan and the house rules; have it write `critique-vN.md` (the taste rubric score from `references/taste.md` §6, blocking issues with root cause in the source, a transition spec table, a checklist). Fix the top three problems and re-score, three rounds at most. Fix every blocking issue, re-snapshot, and review the strips yourself before showing anything. A pass you have not reviewed frame by frame never reaches the user.

**CHECKPOINT K.** Send the user the key-frame contact sheet (hook, each new or changed layout/graphic at its peak, the ending) with one line per frame on what it shows. Wait for their OK before the full render; their changes here are feedback (step 8). This saves a render cycle per correction.

## 7. Finalize

Render with the pinned CLI into the project. **Backtest the render before anything else**: `python "$SKILL_DIR/scripts/audio_backtest.py" --render <raw.mp4> --voice assets/cut.mp4 --music assets/music/bed_duck.wav --music-under <lo,hi>` must PASS (no silent seconds in speech; voice and music both present; music inside the target dB under the voice), and a frame sample must show every visual layer. Report the numbers to the user. Then `python "$SKILL_DIR/scripts/finalize.py" --render <mp4> --plan projects/<job>/edit-plan.yaml --out outputs/<job>` which: normalizes loudness to the platform target, re-encodes to platform spec, writes `<job>-v<N>.mp4` (never overwrites a previous version), extracts `cover.jpg` from the plan's cover time, writes `captions.srt` from the plan, and drafts `post.md` (caption text, hashtags, AI-disclosure note when needed). Verify the output with ffprobe and a final frame sample.

**CHECKPOINT B.** Give the user the file, what changed vs the last version, anything you could not do, and ask for feedback in their own words (also offer quick ratings: hook / pacing / motion / sound / captions / overall 1–5).

## 8. Learn

Read `references/learning-loop.md`. For every piece of feedback — at checkpoints, mid-run corrections, or a later message about a delivered video:

1. `director_memory.py feedback add --brand <client> --applies generic|client|video` with the verbatim quote, job, version, and the plan items it refers to. **Every note is either generic (how the user wants every video) or about this client.** If the note itself doesn't say ("I always want…" = generic; "she prefers…", "for this channel…" = client), ask the user in one short line before writing rules; with no answer, default to `client`.
2. Translate it into rule changes at that **scope** — `rule add --for client --brand <b>` (scope `brand:<b>`) or `--for generic` (scope `global`); profile/platform scopes for content-type or platform facts — — `rule add` / `rule confirm` / `rule weaken` / `ban`. Generalize the *why*, not the exact pixels.
3. A new rule starts as `candidate`; it becomes `default` after it is confirmed (user repeats it or approves a version that applied it). Contradictions are flagged, not silently overwritten — ask which wins.
4. Apply the change to the current job, re-render, and record the new version in `job.yaml`.

The yaml is the product. A run that delivers a good video but learns nothing from the user's notes is only half done.

## Folder + file map

| Path | Purpose |
|---|---|
| `inputs/<job>/` | raw material from the user (never modified) |
| `projects/<job>/` | HyperFrames project, `job.yaml`, `edit-plan.yaml`, `analysis/`, transcripts |
| `outputs/<job>/` | versioned deliverables + cover, captions, post text |
| `video-director.yaml` (workspace root) | workspace defaults (brand, platform) and overrides |
| `$SKILL_DIR/director.yaml` | global learned memory (rules, profiles, brands, feedback log) |

## References

- `references/workspace.md` — folder contract, input classification, job states, legacy adoption.
- `references/engagement-playbook.md` — researched engagement rules (Reels/Shorts/TikTok/YouTube) with sources and confidence.
- `references/animation.md` — the general animation method: beat tagging, `motion_pick.py`, recipe sources, rules every move follows, audit.
- `references/motion-library.yaml` — 38 moves the picker ranks (do not read whole).
- `references/web-capture.md` — Playwright: brand from a website, UI/site recordings, screenshots.
- `references/layouts.md` — speaker layouts per beat (full, overlay, split, PiP bubble, cutaway, cut-out, full text): when to use each, variety and handoff rules.
- `references/taste.md` — the decision mechanism: dials, dealt directions, idea sentence, tells, scored look-and-fix loop.
- `references/directions.yaml` — the direction library `taste.py` deals from (do not read whole).
- `references/edit-plan.md` — `edit-plan.yaml` schema with an example.
- `references/motion-recipes.md` — seek-safe GSAP/HyperFrames patterns for every plan item type.
- `references/media-generation.md` — Codex images, fal video/images (cost flow), whisper GPU, SFX library, music, disclosure.
- `references/hyperframes-routing.md` — which HyperFrames skill/workflow per need, plus hard-won gotchas.
- `references/learning-loop.md` — feedback → rule mapping, scopes, confidence, conflicts, yaml schema.

## Scripts

| Script | Use |
|---|---|
| `workspace.py` | init / scan / new / adopt jobs |
| `director_memory.py` | resolve rules, log feedback, add/confirm/weaken rules, params |
| `analyze_media.py` | probe, loudness, scene cuts, gridded contact sheets |
| `cut_check.py` | verify planned cuts against speech energy (gate before cutting) |
| `motion_pick.py` | pick ranked moves per beat; audit a plan's animation variety |
| `brand.py` | brand intake: import a kit/logo/site answers into director.yaml, template, show, set, contrast check |
| `taste.py` | dials → pacing targets; deal / choose a direction sheet |
| `plan_lint.py` | safe zones, keep-outs, cadence, caps, paid approvals, taste targets + tells |
| `build_captions.py` | caption clips from `transcript.clean.json` into the composition |
| `frame_scan.py` | find corrupted frames (black blocks at take joins) and print the repair |
| `outpaint_fill.py` | full-bleed 9:16 still from any photo (Codex outpaint + seamless paste-back) |
| `music_bed.py` | voice-carved, lightly ducked music bed at a measured level under the voice |
| `audio_backtest.py` | post-render gate: silence, stem presence, music level under speech |
| `finalize.py` | loudness, export spec, versioned file, cover, captions.srt, post.md |
