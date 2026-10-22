# Workspace contract

One folder holds many videos. Every video is a **job** with a slug (kebab-case, e.g. `product-demo-1`, `cafe-promo-oct`). Work is input → output: the user drops material into `inputs/<job>/`, you build in `projects/<job>/`, you deliver into `outputs/<job>/`.

```
<workspace>/
├── video-director.yaml        workspace defaults: brand, platform, language, overrides
├── brands/                   brand kits, one folder per brand (logo, fonts, brand.yaml, guidelines); shared by all jobs
│   └── <brand>/
├── inputs/
│   └── <job>/                 the user's material — read-only for you
│       ├── *.mp4|mov|mkv|webm   footage (one or many takes)
│       ├── *.mp3|wav|m4a        voiceover / music the user supplies
│       ├── *.png|jpg|webp|svg   logos, product shots, photos, screenshots
│       ├── *.ttf|otf|woff2      brand fonts
│       ├── brand/ or brand.yaml|brand.md   a brand kit for this job (import it with brand.py)
│       ├── *.srt|vtt|json       existing transcripts/subtitles
│       └── brief.md / details.md / notes.txt / *.pdf / *.docx   what the user wants
├── projects/
│   └── <job>/                 HyperFrames project (editable in Studio) + director files
│       ├── job.yaml             brief, status, versions, feedback refs
│       ├── edit-plan.yaml       the plan (source of truth for the edit)
│       ├── analysis/            analysis.json, contact sheets
│       └── index.html, compositions/, assets/ ...
└── outputs/
    └── <job>/
        ├── <job>-v1.mp4, <job>-v2.mp4 ...   never overwrite a version
        ├── cover.jpg, captions.srt, post.md
        └── notes.md               what changed per version
```

## Identifying inputs

`scripts/workspace.py scan` classifies every file by extension and probes media with ffprobe:

| Class | Extensions | How to treat it |
|---|---|---|
| footage | mp4 mov mkv webm m4v avi | primary source if it has a face/voice or is the longest; others are b-roll or alternate takes — look at them |
| audio | mp3 wav m4a aac flac ogg | voiceover if speech, music bed if music (listen via transcription: speech → words) |
| image | png jpg jpeg webp svg gif heic | logo if name/shape says so (transparent PNG/SVG, "logo" in name), otherwise b-roll/product |
| font | ttf otf woff woff2 | brand font — embed with @font-face |
| transcript | srt vtt json | trust over whisper when present |
| details | md txt pdf docx rtf | read fully; they carry the brief, script, names, CTA, do/don't |

A details file may have YAML frontmatter; recognised keys: `platform`, `profile`, `brand`, `brand_kit` (path or website URL), `language`, `goal`, `audience`, `length`, `cta`, `keep`, `avoid`, `deadline`. Free text is equally valid — extract the same fields.

## Brand input

A brand can arrive in four ways. Each one ends as `director.yaml → brands.<slug>` via `scripts/brand.py`:

1. A kit folder: `brands/<slug>/` or `inputs/<job>/brand/`. It holds a logo (svg/png; "logo" in the filename wins), font files, guidelines, and `brand.yaml` or `brand.md`. Import it with `brand.py import <folder>`.
2. A website URL in `brand_kit:` or in chat. Read the site, then import its logo with `--url` and `--set` values for the colours, fonts and tone.
3. Plain words in chat. Turn them into `--set` values, or run `brand.py template --id <slug>` so the user can fill in a file.
4. Nothing. Use neutral defaults and ask at checkpoint A.

An imported brand is reused by every later job (`brand: <slug>` in the brief or in `video-director.yaml`). Re-import the kit, or use `brand.py set`, when it changes.

If there are no details at all, infer from the footage + workspace defaults + memory, and confirm at checkpoint A.

## Job states (`job.yaml → status`)

- `new` — inputs exist, no project.
- `planned` — plan written, waiting for checkpoint A.
- `building` — approved, in progress.
- `delivered` — an output version exists and no newer feedback.
- `revising` — feedback logged after the last delivered version.

`workspace.py scan` derives the state from files when `job.yaml` is missing.

## Legacy / loose files

Files at the workspace root (e.g. `video.mp4`, `edited-video.mp4`, an old project folder) belong to no job. `workspace.py scan` lists them and suggests a job slug. Moving the user's files is their decision: propose the move, and run `workspace.py adopt --job <slug> <files...>` (moves inputs; `--project <dir>` moves an existing HyperFrames project; `--output <file>` files a previous render as `v0`) only after they agree.

## Batch

"Do all new videos" → process jobs one after another, each with its own checkpoint A (plans can be presented together in one message to save the user time), building only after approval.
