# video-director

An agent skill for Claude Code and Codex that works like a senior video editor. Drop footage into `inputs/<job>/` and it handles the rest:

- **One brand per client**: say "a video for Sara" and it loads Sara's brand, rules and taste.
- **Takes the brand as input**: a kit folder, a website, or a few words. It imports the logo, colours (extracted from the logo if you give none), fonts, voice, CTA and do/don't rules, and remembers them for every later video.
- **Plans** the edit as data (`edit-plan.yaml`): cuts, camera moves, captions, graphics, b-roll, SFX, music, ending and cover.
- **Chooses how the speaker appears in each moment**: full frame, overlays, split screen, a small talking bubble over a full-width visual, cutaways, a cut-out speaker, or full-screen text. The choice follows what each beat says.
- **Animates each beat with a fitting move** from a library of 38 moves (text, emphasis, data, diagrams, camera, overlays, b-roll, UI, transitions, endings). Moves are ranked per beat for fit and variety, and each is built from tested HyperFrames recipes.
- **Reads websites and records UI** with [Playwright](https://github.com/microsoft/playwright-cli): it takes a client's brand from their site, records product flows, and captures page screenshots.
- **Decides the look** with a taste engine instead of the defaults every generated edit shares.
- **Builds** with [HyperFrames](https://github.com/heygen-com/hyperframes) and **generates** images and short AI clips. Paid generation always waits for your approval and a cost estimate.
- **Checks** its work against platform safe zones, pacing, loudness and audio backtests, and runs a critic loop on key frames.
- **Learns**: every piece of feedback becomes a rule in `director.yaml`. It is scoped either to all clients (generic) or to one client. When a note's scope is unclear, the agent asks.

It covers Instagram Reels, TikTok, YouTube Shorts and long-form YouTube, across talking heads, explainers, promos, tutorials and montages.

## Install

With the [`skills`](https://github.com/vercel-labs/skills) CLI:

```bash
npx skills add rsmed31/video-director-skill
```

Or with the bundled installer:

```bash
npx video-director-skill            # ~/.claude/skills/video-director
npx video-director-skill --codex    # ~/.codex/skills/video-director
npx video-director-skill --project  # ./.claude/skills/video-director
```

Re-running the installer upgrades the skill but **keeps your `director.yaml`** (your learned memory). New defaults are written next to it as `director.starter.yaml`.

Then install the skills it works with:

```bash
npx skills add heygen-com/hyperframes
```
```bash
npx skills add microsoft/playwright-cli
```

Playwright is optional. It needs `npm install -g @playwright/cli@latest` and is only used for website brand extraction and UI recordings.

**Requirements:** Python 3 with PyYAML (`pip install pyyaml`), ffmpeg/ffprobe, and Node 22+. Optional: a GPU build of whisper.cpp for transcription, the Codex CLI for free images, and the fal MCP for paid image and video generation.

## Use

In a folder for your videos:

```
inputs/<job>/     your footage, logo, brief.md   (never modified)
projects/<job>/   the HyperFrames project, plan, analysis
outputs/<job>/    <job>-v1.mp4, cover.jpg, captions.srt, post.md
```

Ask your agent "edit the new video in inputs" or "make a 30 s TikTok promo from inputs/app-launch". It stops at three checkpoints:

- **A. Plan.** The direction, the idea and the structure, plus any paid generation with its cost.
- **K. Key frames.** Stills of the hook, each new layout and the ending, before any full render.
- **B. Final file.** The delivered video and a request for your feedback.

## Brand input

Put a kit in `brands/<name>/` or `inputs/<job>/brand/`. It can hold a logo, font files, guideline PDFs, and an optional `brand.yaml` or `brand.md`. You can also give the agent your website, or just describe the brand in chat. It runs:

```bash
python skills/video-director/scripts/brand.py import brands/acme      # or: template --id acme
```

This stores `brands.acme` in `director.yaml`: palette (with a contrast check), fonts, logo and placement, voice (words to use or avoid), CTA, handles, visual do/don't, and optional taste dials. From then on:

- the brand's colours and fonts replace the dealt direction's palette and type
- the plan checker makes sure the logo appears and no banned word reaches the screen
- feedback about the brand is learned at brand scope

## Animation

`scripts/motion_pick.py pick --beat number --plan edit-plan.yaml` ranks moves for a beat. It weighs:

- fit to the beat (hook, claim, number, comparison, process, demo, punchline, and so on)
- the motion dial
- the art direction
- what the plan already uses, so moves don't repeat

Each move points to real recipes in `/hyperframes-animation` or the registry. `motion_pick.py audit` and the plan checker flag repeats, low variety and moves that don't fit the dial. The method is in `references/animation.md`.

## Speaker layouts

How the speaker shares the frame is chosen per beat (`references/layouts.md`):

| Layout | When |
|---|---|
| full speaker | feeling, opinion, the hook line, the CTA |
| speaker + overlay | a keyword, a name, one number |
| split screen | data and diagrams the speaker reacts to |
| PiP bubble | screen recordings, UI and maps that need the full width; the speaker keeps talking in a small bubble at the bottom |
| cutaway | a concrete thing or action being described |
| cut-out speaker | intros and section openers in front of a graphic |
| full text | the hook card, chapter titles |

The plan checker enforces:

- lengths that fit each layout
- a safe-zone position for the PiP bubble
- variety: no layout three times in a row
- the speaker visible at least 70% of the time in talking-head videos

## The taste engine

A model asked to edit a video produces the average edit: a whoosh on every cut, word-pop captions, emoji stickers and a "Did you know?" hook. The taste engine adapts the decision mechanism of [taste-skill](https://github.com/Leonxlnx/taste-skill) (MIT) to video:

1. **Dials.** Three settings from 1 to 10: `energy` (cut pace), `motion` and `density`. Baselines are set per profile and brand, and your own words override them ("calmer", "punchier"). The dials turn into concrete pacing targets that the plan linter enforces.
2. **Dealt directions.** `scripts/taste.py draw` deals 3 of 12 researched directions, such as split-screen teacher, documentary calm, kinetic explainer, data desk or whiteboard builder. The agent picks the one that can carry something only this subject has. Redraws need a stated reason.
3. **An idea sentence.** "In this video, *[something only this subject has]* becomes *[the device the direction calls for]*." It must pass a competitor test: if the sentence would also fit a competitor's video, it isn't specific enough.
4. **A list of tells** that the linter flags.
5. **A scored loop.** The critic scores key frames against a rubric, fixes the top three problems, and repeats for at most three rounds.

Details are in [`skills/video-director/references/taste.md`](skills/video-director/references/taste.md).

## Memory

Feedback is either **generic**, meaning how you want every video, or **client-specific**, meaning one client's taste. The agent asks when it can't tell. Client numbers, such as one client's preferred music level, live in `brands.<client>.profile_overrides`.

`director.yaml` ships as a starter memory:

- platform specs and safe zones
- edit profiles with their dial baselines
- an example brand
- research-backed default rules

The feedback log starts empty. As you give feedback, the agent logs it verbatim and turns it into scoped rules (`scripts/director_memory.py`). A new rule starts as a candidate and becomes a default once you confirm it.

## License

MIT. The taste engine adapts [taste-skill](https://github.com/Leonxlnx/taste-skill) (MIT).
