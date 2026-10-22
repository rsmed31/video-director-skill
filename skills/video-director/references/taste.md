# Taste: how the director decides

An edit made by a model usually looks like the average of every edit it has seen: a whoosh on every cut, word-pop captions in three colours, an emoji sticker per sentence, a punch-in on every line and a "Did you know?" hook. Nothing in it is wrong, and none of it was decided.

This file replaces those defaults with decisions. The method is adapted for video from [taste-skill](https://github.com/Leonxlnx/taste-skill) (MIT). From its v1 come **three dials that drive concrete rules**. From its v2 come **dealt directions you choose between, an idea taken from the subject, a list of tells, and a look-and-fix loop**. Run it at step 3 (Plan), before you write any `edit-plan.yaml` items.

## 1. Set the dials

Three dials from 1 to 10 set the job's taste:

| Dial | 1 | 10 |
|---|---|---|
| `energy`: cut pace | cuts on breaths, held reactions | jump cuts mid-sentence, a change every 2 s |
| `motion`: camera and overlay movement | locked-off frame, slow drift at most | camera never still, every overlay enters and exits |
| `density`: things on screen at once | the speaker and nothing else | a full information layout (rail, board, chart) |

```bash
python "$SKILL_DIR/scripts/taste.py" dials --profile <p> --brand <b> [--set energy=7,motion=4]
```

- The **baseline** comes from `director.yaml`: `profiles.<p>.taste`, then `brands.<b>.taste`. Later values win.
- **Listen to the user's words** and pass them as `--set`. Don't ask the user to edit a file. Rough mapping: "calmer / less busy" means motion and density −2. "Punchier / faster" means energy +2. "Cleaner" means density −2. "More motion / zooms" means motion +2. "Cinematic" means energy −2 and motion +1.
- The script prints **derived targets**: max static seconds, hook timing, punch-ins per 30 s and their scale, minimum layout-transition length, overlays on screen, graphics per minute, and SFX per 10 s. It also prints the threshold rules that switch on, for example "motion ≤ 3: no whips". Copy the dials into `edit-plan.yaml → taste.dials`. `plan_lint.py` then checks the plan against the derived targets.
- **Memory wins over dials.** A ban or a confirmed rule in `director.yaml` is never overridden by a dial. Example: "transitions are smooth, never snappy" holds even at motion 9.
- When feedback is about intensity ("too much", "too slow"), adjust the dial at the right scope with `director_memory.py param set --path brands.<b>.taste.motion --value 4 --evidence fb-…`. Don't patch individual numbers.

## 2. Inventory the subject

Before choosing a look, list 8–12 things in your notes that belong to this video's subject and to no competitor. Look for:

- the speaker's real objects, tools, room and gestures
- the numbers they actually say
- the place they are in
- the one constraint they live with
- their materials and colours
- the printed things of their world: a menu, a ticket, a label, a schedule, a receipt
- the words they repeat

The idea comes from this list, and so do the b-roll and image-generation queries.

## 3. Deal the direction

```bash
python "$SKILL_DIR/scripts/taste.py" draw --profile <p> [--tone <t>] --have <footage,speech,data,photos,product_ui,music,logo> [--want energy=8]
```

The script deals **three of twelve** researched directions from `references/directions.yaml`. It weights them by profile, tone, the user's requested dials and the assets that really exist.

Asked to invent a look, a model picks the category default every time. Choosing among dealt options is what breaks that habit.

1. Hold each dealt direction against the inventory and ask: which signature move can carry something only this subject has?
2. Choose that direction, not the most familiar one. Write one line on why.
3. Write the sheet:

   ```bash
   python "$SKILL_DIR/scripts/taste.py" sheet --direction <id> --profile <p> --seed <seed> --reason "<why>" --out projects/<job>/direction.yaml
   ```

The sheet is the art direction for the job. It sets the signature move, the transition grammar, the caption style, the graphics language, type, sound and palette, plus the direction's own `avoid` list. It also blends the direction's dials with the baseline. **Adopt it.** Don't blend it with the edit you would have made anyway.

**Redraw only for a reason you can state.** Valid reasons: the direction contradicts a brand rule, needs an asset that doesn't exist, or the user asked for a different feel. To redraw, run `draw --exclude <id,…>` and record each redraw and its reason in `direction.yaml`. Never redraw to get something more comfortable.

A brand palette or font from `director.yaml` always replaces the sheet's palette or type. The sheet still sets the proportions (one ground, one ink, one accent).

## 4. Write the idea sentence

Fill in both blanks from the inventory before planning any item:

> In this video, **[something only this subject has]** becomes **[the device the signature move calls for]**.

Examples:

- "The presenter's handwritten recipe card becomes the board that builds across the whole video" (whiteboard-builder).
- "The café's stamp card becomes the chapter card" (editorial-magazine).

**Competitor test:** put the nearest competitor in the sentence, such as another coffee channel's Reel or another app's promo. If the sentence still works, the idea belongs to the category, not the subject, so find another. "Clean and engaging" is not an idea.

**One live thing.** Give the video one moment that rewards attention because it comes from the idea. Examples: a callback the hook set up, a number that resolves on screen, or the diagram completing at the end. Every winning edit has one, and viewers name it first. It goes in the plan as an item, not as decoration added later.

Write the result to `edit-plan.yaml → taste` (schema in `edit-plan.md`). Show it at checkpoint A in two lines: the direction with the reason, and the idea sentence.

## 5. Tells: generated-edit habits, and what replaces them

These are banned unless the direction sheet or the user explicitly calls for one. `plan_lint.py` flags the ones it can measure.

| Tell | Instead |
|---|---|
| A whoosh or impact on every cut | SFX only on actions (sfx_map), capped by `derived.sfx_per_10s`; hard cuts stay silent |
| Word-pop captions in several colours, every word animated | The sheet's caption style; at most 1 highlighted word in 10, in one accent |
| Emoji stickers, a "subscribe" bell, a pointing-hand GIF | Stickers drawn from the inventory (its real objects), or nothing |
| A punch-in on every sentence | Punch-ins on claims and punchlines, within `derived.punch_in_per_30s_max` |
| Glitch, VHS, light-leak or flash transitions as filler | The sheet's transition grammar; caps in `director.yaml` |
| A "Did you know?" or "Wait for it" hook | The strongest real line from the transcript, on frame 0 |
| Generic stock b-roll (typing hands, city timelapse, handshake) | Footage or generated images of the inventory's things |
| Gradient text, drop shadows on captions, glowing outlines | Flat text on a flat backing, in the palette |
| Invented statistics or fake UI | Real numbers only, otherwise qualitative labels; real interface fragments only |
| A centred static title card that fades in and out | A title that builds with the sheet's signature move |
| The same layout for every section | Neighbouring sections differ in layout or scale |

## 6. Look, score, fix (three rounds at most)

`lint` and `check` passing only means nothing banned was measured. It does not mean the edit is good. At QA, run the critic described in SKILL.md §6 on the key-frame and transition strips. Have it score the edit with this rubric (1–10 each):

| Criterion | Weight | Cap |
|---|---|---|
| Hook: frame 0 to 3 s stops the scroll | 20% | — |
| Idea: the idea sentence is visible, and the competitor test passes | 15% | 5 if there is no idea sentence |
| Pacing: matches the dials, no dead stretches | 15% | — |
| Motion: motivated, smooth, follows the sheet's grammar | 15% | 4 if any transition is snappy against the rules |
| Readability: captions, labels and safe zones | 15% | 3 if anything covers a face or burned-in text |
| Sound: voice clear, bed audible, SFX mapped | 10% | 3 if a backtest fails |
| Ending: loop, CTA, preserved source ending | 10% | — |

Write the scores and the **top three problems** into `critique-vN.md`, fix those three, re-snapshot and score again. Stop after three rounds, or earlier when the weighted score is 8 or more with no capped criterion. Report the final score at checkpoint K, including what still falls short.

Judge only the frames. If a problem is visible in a snapshot, it is real, whatever the source says.
