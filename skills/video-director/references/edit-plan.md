# edit-plan.yaml

The plan is the single source of truth for an edit. Write it before any HTML, lint it, show it at checkpoint A, build from it, and map feedback back to its item ids. Times are **output-timeline seconds** unless a field says `src_` (source media seconds). Boxes are `[x, y, w, h]` in canvas pixels.

```yaml
job: coffee-tips-1
version: 2                     # bump on every re-plan after feedback
platform: instagram_reels
profile: talking_head_edu
brand: example-brand
canvas: [1080, 1920]
duration: 83.75
style_suffix: "Photorealistic editorial photo, soft daylight, warm beige + muted teal ..."   # shared by all generated media

taste:                          # decided before any item (references/taste.md); taste.py sheet writes direction.yaml
  dials: {energy: 6, motion: 7, density: 5}      # from `taste.py dials`, user's words applied
  direction: split-teacher                       # dealt by `taste.py draw`, chosen against the inventory
  reason: "the presenter explains with gestures toward a chart; the split keeps the face while the chart builds"
  redraws: []                                    # [{from: id, reason: ...}] - every redraw with its stated reason
  inventory: ["their handwritten recipe card", "the café's stamp card", "'four minutes' repeated 4x"]
  idea: "In this video, the presenter's handwritten recipe card becomes the board that builds across the whole video"
  live_thing: "the recipe card completes on the last line and loops to the hook"

story:                          # what the video says, in sections (drives everything else)
  - {id: s0, start: 0, end: 12.75, beat: hook, summary: "Why does your coffee taste bitter? = the grind is too fine"}
  - {id: s1, start: 12.75, end: 25.4, beat: setup, summary: "Three things decide taste: grind, water temperature, brew time"}

keepout:                        # from contact sheets: faces, burned-in text, key action
  - {start: 0, end: 81.5, box: [0, 0, 760, 1250], what: face+hair (varies, worst case)}
  - {start: 0, end: 7, box: [560, 160, 520, 420], what: burned-in title}

cuts:                           # source ranges laid end to end (pacing)
  - {id: c1, src_start: 0, src_end: 12.75, why: hook intact}
  - {id: c2, src_start: 13.0, src_end: 81.8, why: removed 0.25 s dead air, rules: [R-change-cadence]}

camera:                         # keys on the camera wrapper (scale/x/y), see motion-recipes#camera-rig
  - {id: k1, t: 0, scale: 1.1, to: 1.0, dur: 1.6, ease: power3.out, why: opening settle}
  - {id: k2, t: 12.75, scale: 1.12, cut: true, why: mask jump cut, rules: [R-motivated-motion]}

captions:
  source: projects/coffee-tips-1/transcript.clean.json
  style: word_pop
  band: [1080, 1250]
  chunks:                       # optional explicit overrides; otherwise generated from transcript
    - {start: 0.0, end: 4.4, text: "Your coffee tastes <b>bitter</b>?"}

graphics:                       # motion graphics: titles, steps, data, callouts, stickers
  - id: g-hook
    type: kinetic_title          # kinetic_title | name_tag | section_title | step_list | data_build_zoom | callout | sticker | progress_bar | cta
    motion: word-stack-build     # move id from motion-library.yaml (motion_pick.py pick --beat hook); custom:<name> if hand-built
    start: 6.6
    dur: 5.95
    box: [54, 1400, 900, 300]
    content: {kicker: "Bitter =", lines: ["grind too fine"]}
    sfx: [{key: sparkle, at: 6.6}]
    why: answers the spoken question the instant it is asked
    rules: [R-hook-text-frame0]

broll:
  - id: b1
    kind: still_animated         # still_animated | ai_clip | user_clip
    asset: assets/kitchen.jpg
    gen: {provider: codex, prompt: "kitchen counter with a pour-over kettle and a scale ... + style_suffix"}
    start: 15.3
    dur: 5
    layout: card                 # card | split | fullframe | pip
    box: [54, 1250, 400, 560]
    motion: motion-recipes#card-entrance
    sfx: [{key: pop, at: 15.35}]
    why: illustrates 'grind, water, time'

transitions:
  - {id: t1, at: 25.4, type: section_slam, sfx: [riser-to-hit], why: chapter 01}

audio:
  voice: {source: take, keep: true}
  music: {asset: null, db_under_voice: -20, duck: true}
  sfx: []                        # standalone cues not owned by an item above

ending:
  preserve_source_ending: true
  hold: {start: 81.55, dur: 2.2, freeze: assets/last-frame.jpg}
  cta: {type: follow_series, text: "Part 2 soon", start: 81.6}
  loop_to_hook: false

layouts:                        # speaker layout per beat (references/layouts.md); gaps = full_speaker
  - {id: L1, kind: text_full, start: 0, end: 1.6, why: hook card over the opening still}
  - {id: L2, kind: full_speaker, start: 1.6, end: 9.0, why: personal claim, face matters}
  - {id: L3, kind: speaker_overlay, start: 9.0, end: 11.5, items: [g-kw1], why: one keyword}
  - {id: L4, kind: split, start: 17.14, end: 29.2, items: [g-r1, g-r2], why: two graphs back to back, reaction matters}
  - {id: L5, kind: pip_speaker, start: 33.0, end: 41.0, box: [70, 900, 320, 320], items: [b-ui], why: screen demo needs full width}
  - {id: L6, kind: cutaway, start: 41.2, end: 44.4, items: [ai-b2], why: "'the gooseneck kettle' - a concrete noun"}
  # captions follow the head in every kind (above the bubble in pip_speaker)

grade: {tool: media-treatment, targets: ["#take", "#take2", "#hold"], payload: {preset: skin-soft, intensity: 0.8}}
upscale: {provider: fal, model: fal-ai/bytedance-upscaler/upscale/video, tier: standard, est_usd: 0.39, approved: false}

cover: {t: 8.9, why: hook line + title visible, face centered}

cost:
  free: [codex images x8, bundled sfx]
  paid: [{provider: fal, model: minimax/h3-max/image-to-video, items: 2, seconds: 8, est_usd: 0.6, approved: false}]

open_questions:
  - Presenter name spelling?
```

## Lint expectations (`scripts/plan_lint.py`)

- Every graphic, broll and caption box must sit inside the platform safe zone and avoid the right rail, unless it has `allow_unsafe: <reason>`. Full-frame layouts are exempt.
- No box may overlap a `keepout` box active at the same time by more than 4% of the box area, unless `allow_overlap: <reason>`.
- A text item (graphic or caption) must be on screen within `profile.hook_change_by_s`, and some change must occur by then.
- No gap longer than `profile.max_static_s` without an event (camera key, cut, graphic, broll, caption emphasis, transition).
- Effect counts per minute must stay within `caps`.
- Every graphic has a `motion:` move; `motion_pick.py audit` finds no repeats, low variety or moves far from the motion dial.
- `layouts` kinds and lengths fit references/layouts.md; the PiP bubble is 260-420 px inside the safe zone; the speaker is visible >= 70% in talking-head profiles; no non-default kind 3x in a row; >= 3 kinds per 60 s at density >= 4.
- `taste` block filled (direction, idea); dial targets for punch-ins, scale, layout transitions, graphics and SFX density; tells (whoosh on every cut, emoji, stock hook phrases).
- `brand` exists in director.yaml; its logo is placed; no word from `brand.voice.avoid` appears on screen.
- `cost.paid` items without `approved: true` are listed as blockers before the build.
- `ending.preserve_source_ending` must agree with the cuts (the last cut must reach the source end).
