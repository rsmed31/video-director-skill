# Media: sourcing and generation

Order of preference:
1. User inputs (`inputs/<job>/`).
2. Project and global media cache. Run `npx --yes hyperframes@<pin> media-use resolve --type <t> --intent "..." --candidates --project .`; you judge semantic fit, then `--reuse <sha>`.
3. Bundled library (SFX).
4. **Free generators:** Codex images, local whisper, HyperFrames TTS when available.
5. **Paid generators (fal):** only after the user approves the cost at checkpoint A (`preferences.paid_generation: always_ask`).

Write every generated or downloaded asset into `projects/<job>/assets/…`. Record its prompt and provider in the plan item (`gen:`), so revisions can regenerate consistently.

## Images: Codex (free, user's ChatGPT plan)
- Codex is not on PATH. Prepend its bin dir in the same shell:
  `export PATH="$HOME/.codex/packages/standalone/releases/<ver>/bin:$PATH"` (find `<ver>` with `ls ~/.codex/packages/standalone/releases/`). Check `codex login status`.
- Generate: `npx --yes hyperframes@<pin> media-use resolve --type image --provider codex --intent "<subject>. <style_suffix>" --project .` writes `.media/images/image_NNN.png`.
- Run several in parallel with `&` + `wait`, inside one shell where the function is defined (a backgrounded `&&` chain loses the function).
- Downscale for the composition (`ffmpeg -i in.png -vf scale=840:-1 -q:v 3 assets/x.jpg`), then contact-sheet them and **look** before using them.
- Keep one `style_suffix` per job (brand `ai_media_style` when set) so the images match each other and the footage palette.
- Ask for no text or logos inside generated images; you overlay text yourself.

## Short AI video clips: fal (paid; always ask)
1. Pick the model with `mcp__fal__recommend_model` (`operation: image-to-video` or `text-to-video`, `requirements: {aspect_ratio: "9:16", duration_seconds: 4, audio_mode: "none"}`). The curated default for image-to-video (2026-10) is `minimax/h3-max/image-to-video`; `alibaba/wan-3.0-prime/image-to-video` honours `aspect_ratio: 9:16` explicitly. `bytedance/seedance-2.5/*` tends to reject faces.
2. Price it with `mcp__fal__get_pricing` or `estimate_cost`. Put the line in `edit-plan.cost.paid` and present it at checkpoint A: model, number of clips, seconds, estimated USD.
3. After approval: image-to-video from a Codex still works best (control plus consistency). Upload with `mcp__fal__upload_file`, then `submit_jobs` (batch), `wait_for_jobs`, then download the MP4s into `assets/ai/`.
4. Prompt motion explicitly: camera move, subject action, "no text, no cuts, no audio". Use 3–5 s clips; trim the first ~0.4 s.
5. The fal tools' own rules: never prepend `fal-ai/` to IDs, never claim a payment or credit went through, keep request ids for retries instead of resubmitting.
6. Negative prompts are not reliable: image-to-video models can ignore "no text" or "no blood" after the first second. Use only the first ~1.5 s of a sensitive shot, or show it small inside a card; strip-check every clip at 1 fps before use.

## Speech → transcript
- **GPU whisper:** a CUDA build of `whisper-cli` on PATH (record its location in `director.yaml → tooling.whisper`); recent GPUs may run through driver JIT, so the first run per session is slower.
- Command: `npx --yes hyperframes@<pin> transcribe <video> --engine whisper --model large-v3 --language <iso> --json` writes `transcript.json` (word-level).
- The HyperFrames auto-build of whisper.cpp fails on Windows because it checks for `whisper-cli` without `.exe`. The shim is the fix. CPU fallback: `~/.cache/hyperframes/whisper/whisper.cpp/build/bin/whisper-cli.exe`.
- Whisper hallucinates after speech ends (subtitle credits, "thanks for watching"); drop words after the last real speech.
- It mangles code-switched terms. Clean them by hand into `transcript.clean.json` and keep the timings.
- **Dialects and code-switched speech:** the HyperFrames wrapper can normalise a dialect into the standard language and interpolate timings (one "word" spanning 10 s). Use whisper-cli directly with per-word stamps and a prompt naming the dialect plus the domain terms the speaker uses:
  `whisper-cli -m ~/.cache/hyperframes/whisper/models/ggml-large-v3.bin -f a16.wav -l <lang> -ml 1 -sow -oj -of words --prompt "<dialect name> ... <domain terms>"` on a 16 kHz mono loudnorm'ed wav.
  Re-run with the second language (`-l <other>`) on short code-switched spans; borrowed terms come out clean. Keep a list of recurring mis-renderings per client in their brand notes.
  ggml word stamps drift +-0.5 s: snap chunk starts to speech onsets from an energy envelope (`scripts/cut_check.py` prints quiet runs).
  Ask the user to confirm any line you reconstructed; mark those chunks `provisional` in `transcript.clean.json`.

## SFX
- The bundled library (offline, free) lives in `~/.claude/skills/media-use/audio/assets/sfx/`, indexed by `manifest.json`:
  - whooshes: `whoosh`, `whoosh-short`, `whoosh-cinematic` (5.5 s build)
  - UI sounds: `pop`, `click`, `click-soft`, `key-press`, `typing`, `ping`, `notification`, `chime`, `error`
  - accents: `sparkle`, `riser` (10.03 s), `impact-bass-1/2`, `glitch-1/2/3`
- Copy the files you use into `projects/<job>/assets/sfx/`. Read `manifest.json` descriptions for placement hints.
- When a needed sound is missing (e.g. a vinyl crackle or a camera shutter), say so. A credentialed HeyGen catalog (`hyperframes auth login`) gives retrieval of the long tail. fal `sound-effects` generation is paid, so ask first.

## Music bed
- `media-use resolve --type bgm --intent "<mood>, instrumental, no vocals"` needs a HeyGen sign-in (free usage). The local MusicGen fallback needs `pip install transformers torch soundfile numpy`.
- fal (paid, ask first): `elevenlabs/music/v2.5`, $0.60/min (56 s ~ $0.56), `force_instrumental: true`, `music_length_ms` = root duration + 1 s. Prompt for "consistent low energy, no drops, sits under a voice"; it delivers a very even bed (LRA ~1 LU).
- Mix it with `scripts/music_bed.py` and verify with `scripts/audio_backtest.py` (see motion-recipes#music-bed for the level the user wants).
- With none available, leave the bed out and say so at checkpoint B rather than faking one.

## Upscaling low-res footage (paid, offer when source < 1080 wide)
- `fal-ai/bytedance-upscaler/upscale/video`, `enhancement_tier: standard` ($0.0072/s, 54 s ~ $0.39; `pro` is 10x), `enhancement_preset: ugc` for phone selfies, `fidelity: high` keeps the face natural, `target_resolution: 1080p`. A 54 s 576x992 phone clip took ~4.5 min and returned 1080x1860 with audio, same duration.
- Alternatives: FlashVSR ~ $1.7, FLUX video upscale $0.045/s.
- Upscale the **source**, then rebuild the cut master with the same trims (keep the already-processed voice track: map video from the upscale and audio from the old cut master), lighter `unsharp` (0.25), and verify alignment with SSIM against the old master at several times (~0.99).
- Inspect a face close-up old-vs-new before using it (identity must be unchanged).

## Full-bleed stills from non-9:16 photos
- `python "$SKILL_DIR/scripts/outpaint_fill.py" --photo inputs/<job>/photo.png --out assets/img/photo_9x16_fill.png`: Codex outpaint (free; `codex exec -s workspace-write --skip-git-repo-check "<prompt>" -i photo.png` with the prompt BEFORE `-i`) plus a colour-matched, feathered paste-back that removes the generator's tone step and border line.
- Fallback (paid, ask): `bria/fibo-edit-1.5/expand` $0.04/image, keeps the original pixels.
- Give the still the same `data-color-grading` as the footage so skin matches and both loop copies are identical.

## Grading footage for Reels
Use `hyperframes media-treatment` (read `/media-use` references/media-treatments.md first). Natural-Portrait base pushed for Reels; the conservative recipe values were invisible on phone footage:
```json
{"preset":"skin-soft","intensity":0.8,"adjust":{"exposure":0.25,"contrast":0.12,"highlights":-0.15,"shadows":0.25,
 "whites":0.02,"blacks":-0.03,"temperature":-0.15,"tint":0.04,"vibrance":0.12,"saturation":0.02},"details":{"vignette":0.12}}
```
Presenter feedback moved the default to: contrast 0.04, intensity 0.65, temperature -0.18, tint 0.05, vibrance 0.04 plus `hueCurves.hueVsSaturation [[10,0],[30,-0.22],[45,-0.15],[60,0]]` and `hueVsHue [[10,0],[30,-4],[50,0]]` so skin is not orange.
Apply to every element showing the footage (`#take`, the split copy, the hold frame, opening/closing stills), `--clear` before re-applying, and judge with a face-crop before/after sheet. Negative temperature removes the yellow-olive cast of indoor phone footage; skin-soft alone warms it.


## Fonts
Bundled families (render offline): Inter, Roboto, Montserrat, Oswald, League Gothic, Archivo Black, Space Mono, IBM Plex Mono, JetBrains Mono, Source Code Pro, Noto Sans JP, …. Any other family, including Arabic ones (Cairo, Tajawal), needs a local file plus `@font-face`. The official source is `https://github.com/google/fonts/raw/main/ofl/<family>/<File>.ttf`; save it to `assets/fonts/`.

## Disclosure and likeness
- Realistic generated scenes, especially of people or real places, get a disclosure line in `post.md` ("Contains AI-generated imagery — enable 'AI info' when posting").
- Never generate or alter the speaker's likeness or voice unless the user explicitly asks.
