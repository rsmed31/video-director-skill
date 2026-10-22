# HyperFrames routing and gotchas

This skill decides *what* to make; the HyperFrames skills decide *how*. Always enter through `/hyperframes`, which routes to a workflow. Pass the plan as the brief, and set `flow: automation`, `storyboard: no` when the plan is already approved.

| Job shape | Workflow | Also load |
|---|---|---|
| Existing footage remix: recut, zooms, overlays, captions, b-roll | `/general-video` | `/hyperframes-core` (cuts, tracks), `/hyperframes-keyframes` (camera), `/hyperframes-animation` (graphics), `/hyperframes-audio` (mix), `/media-use` |
| Plain captions only, footage untouched | `/embedded-captions` | |
| Designed overlays on a talking head, footage untouched | `/talking-head-recut` | |
| Music-driven edit | `/music-to-video` | `npx hyperframes beats` |
| Short motion graphic (<10 s) | `/motion-graphics` | |
| Faceless explainer from text | `/faceless-explainer` | |
| Product or website promo | `/product-launch-video` | |
| Slides or deck | `/slideshow` | |

Before installing or entering a workflow, run `npx --yes hyperframes@<pin> skills update <workflow>`. Search the registry (`catalog --query`) before hand-building any named effect.

## Project hygiene
- Scaffold with `npx --yes hyperframes@latest init projects/<job> --non-interactive --example=blank --skill=general-video`, then copy the source footage into the project. Never reference `inputs/` from the composition, so the project stays self-contained.
- **Version pin:** use the project's own scripts (`npm run check|render|dev`) or `npx --yes hyperframes@<pin>`. A bare `npx hyperframes` can pull a newer version into the npx cache that a running Studio uses. Studio's export then fails with "Cannot find module …/dist/src-XXXX.js". Fix: `preview --stop`, then restart the preview with the pinned version.
- **Upgrade at job start:** `npx --yes hyperframes@latest upgrade --project . --check`, then apply, then `check`. Report old → new in the summary.
- Studio stamps `data-hf-id` attributes into `index.html` when it opens it. They are harmless, but the file then counts as "changed on disk": read it again before writing.
- One sub-composition per section or graphic family keeps Studio usable. The lint warnings `nested_structure_needs_subcomposition`, `timeline_track_too_dense` and `composition_file_too_large` are fine for quick single-file builds; split into sub-compositions for anything you expect to revise.

## Composition contract reminders (each one has bitten a real build)
- Cut, trim and reorder with multiple `<video>` elements sharing one `src` (`data-media-start` + `data-duration` + `data-start`). Sound stays on the video (`data-has-audio="true"`). Every media element needs an `id`.
- Never give a timed `<video>` an ancestor that also has `data-start`. A plain wrapper like `#cam` is fine.
- Don't tween `.clip` elements' visibility or autoAlpha; animate children.
- Root `data-duration` must cover the last clip. When you extend the ending (hold or CTA), raise it.
- Fonts outside the bundled list fail lint (`font_family_without_font_face`); embed them locally.
- Elements built in JS at load time (ticks, repeated decorations) are fine if deterministic. Timed clips and audio must be static HTML.
- `check` also runs a contrast audit. Amber or light text over a white subject can fail even with a dark stroke; lighten the color or add a backing.
- Ken Burns overscan triggers a `container_overflow` info notice. Add `data-layout-allow-overflow` to the image.
- A lint **error** disables the layout and contrast audits ("0 samples"); fix errors first.
- Render length is the root `data-duration`. Rendering at 1080×1920 from 720p footage is fine; the footage upscales and overlays stay crisp.
- A cut master's video stream can be shorter than its audio (52.2 vs 52.3 s): set the video clip's `data-duration` from the **video** stream and start the hold frame there.
- Split-screen copies of footage and overscanned media need `data-layout-allow-overflow`.

## ffmpeg pitfalls (each one shipped a bad version once)
- `afade=t=in:st=X` **mutes everything before X**. For micro-fades at cut points, fade each segment (`afade=t=in:d=0.03` at its start, `t=out` at its end) before `concat`, never one fade on the joined stream. A misplaced fade muted the first 8 s of an early version.
- `loudnorm` outputs 192 kHz internally; add `aresample=48000` right after it, or `sidechaincompress` against a 48 kHz key mis-times and truncates.
- `apad=whole_dur` is unreliable; use `apad=whole_len=<samples>` + `atrim`.
- `alimiter` auto-levels by default (`level=1`), shifting loudness by ~1 dB.
- Single-frame JPG export with `-sseof` failed with mjpeg "non full-range YUV"; use `-vf "select=gte(t,T)" -frames:v 1 -update 1 out.png`.
- `analyze_media.py` silence lists are wrong on quiet phone audio: always run `scripts/cut_check.py` before cutting.
- AAC stems decode with a 1024-sample priming offset (21.3 ms @48k) relative to the render; sample-level comparisons must align first (`audio_backtest.py` does it by cross-correlation).
- In wait loops, grep for the CLI's own success line ("Render complete"), not "error"; render traces contain the word.

## Rendering
- `npx --yes hyperframes@<pin> render --output <project>/renders/<job>-v<N>-raw.mp4`, then run `scripts/finalize.py` for loudness, export spec, cover and captions.
- Typical speed: ~45 s per 80 s of 1080×1920 in drawelement capture mode; screenshot mode is about 3× slower.
- After rendering, read the summary's capture mode and GPU line. If it reports `screenshot` with a software GPU, expect slow renders.
