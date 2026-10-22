# Animation: a general method for strong motion

Good motion is not a fixed set of effects. Each beat gets the move that fits what it says, from a wide library, without repeats, at the job's motion level. Every move is built from tested recipes, not improvised.

## 1. Tag the beats

Go through the cleaned transcript. Tag each beat with what its content does, using the beat names in `motion-library.yaml`:

| Beat | Example | Beat | Example |
|---|---|---|---|
| hook | the opening line | number | "3 weeks", "80%" |
| claim | "fresh beans matter most" | comparison | "before / after", "A vs B" |
| keyword | a term to remember | trend | "it gets worse every year" |
| list / steps | "three reasons" | process / cause_effect | "this leads to that" |
| question / quote | spoken question, citation | concrete_noun / place / name | a thing, a place, a person |
| punchline / emotion | the joke, the feeling | warning / tip | "never do X", "try this" |
| demo / reveal | showing UI or a result | section_change / cta / ending | structure |

Not every beat needs a move. Speech that carries itself gets the camera only. In a talking-head piece, about one beat in two gets an animated element, and the hook and section changes always do.

## 2. Pick the move

```bash
python "$SKILL_DIR/scripts/motion_pick.py" pick --beat <beat> --plan projects/<job>/edit-plan.yaml [--n 3]
```

The script ranks moves on four things:

1. **Beat match.** The move's beats must include this one.
2. **Motion dial.** Its level sits near `taste.dials.motion`.
3. **Direction.** The direction sheet's families get a bonus; for example, data-desk favours data and camera moves.
4. **Variety.** Moves and families the plan already uses get a penalty, and the same move is never used on two consecutive beats.

Take the top pick unless the content clearly suits another one. Write it on the item as `motion: <id>`.

## 3. Build it from recipes

Each move lists its recipes. Build in this order:

1. **Search `/hyperframes-registry`** for the move. A hosted block that already does it beats hand-building.
2. **`hf:<rule>` and `bp:<blueprint>`.** These are rules and blueprints in `/hyperframes-animation`. Compose 2–4 atomic rules on one paused GSAP timeline, and load a blueprint only when the scene has several phases.
3. **`mr:<section>`.** These are this skill's `motion-recipes.md` patterns: camera rig, data-build-zoom, split-screen, captions, transitions.
4. **Hand-build only if nothing fits**, and still follow the rules below. Mark it `motion: custom:<name>`.

## 4. Rules every move follows

- **Three phases.** Entrance, life, exit. While it is on screen it is never frozen: add a slow drift, a breathing scale (≤ 2%) or a progress element. Its exit is designed, not a cut to nothing, unless a hard cut is the point.
- **Timed to the voice.** It lands on the spoken word, within ±0.1 s of the word's onset in the transcript. Data builds one element per spoken beat.
- **One hero per moment.** At most one prominent move at a time. Secondary motion (drift, glow) stays quieter. The overlay count is capped by `derived.overlays_on_screen_max`.
- **Eases.**
  - Entrances: `power3.out`, `expo.out` or `back.out` (springs only for playful moves).
  - Layout changes: `power3.inOut`.
  - Never `linear`, except for scrubs and drifts.
- **Durations.**
  - Entrances: 0.3–0.8 s.
  - Layout changes: at least `derived.layout_transition_min_s`.
  - Holds: long enough to read, at about 3 words per second plus 1 s.
- **Transforms and opacity only.** Pre-compute positions; never animate `width`, `height`, `top` or `left`. This keeps the render deterministic (`/hyperframes-animation` → Critical Constraints).
- **Sound follows motion.** Each move names its SFX. Keep SFX under the voice and within `derived.sfx_per_10s`. A move marked `sfx: none` stays silent.
- **Brand.** Colours come from the brand palette and type from the brand fonts. The client's `visual.dont` list beats any move.
- **Variety.** No move twice in a row. Aim for about one new move per 10 s. Mix at least three families per minute: text, emphasis, data or diagram, camera, overlay, b-roll, ui.

## 5. Check it

- `motion_pick.py audit projects/<job>/edit-plan.yaml` reports missing moves, repeats, low variety, moves far from the motion dial, and a missing ending move. `plan_lint.py` includes this audit.
- After building, run `/hyperframes-animation` → `scripts/animation-map.mjs` on the composition. It finds dead zones, stagger inconsistencies and lifecycle problems.
- Snapshot every move at its entrance, peak and exit, as part of the critic strips in SKILL.md §6. A move that looks wrong in a still is wrong.
