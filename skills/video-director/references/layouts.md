# Layouts: where the speaker goes while the video shows something

How the speaker shares the frame with graphics, b-roll and text is a choice made **per beat**, from what that beat says. It is not one layout for the whole video, and it is not always a split screen. Plan it as a `layouts:` timeline in `edit-plan.yaml`, and `plan_lint.py` checks it.

## The vocabulary

| Kind | What the frame shows | Use it for |
|---|---|---|
| `full_speaker` | The speaker fills the frame; captions sit under the chin. | Emotion, opinion, personal story, the hook line, the CTA. The face is the content. |
| `speaker_overlay` | The speaker stays full frame, with a small element in free space beside the head: keyword callout, sticker, lower third, checklist tick, number. | Short claims, keywords, names, a single number. Under ~3 s of information. |
| `split` | Graphic in the top half and the speaker full-width in the bottom half, whole face visible. Not a boxed card. | Data, diagrams and comparisons that need 4 s or more, where the speaker's reaction still matters. |
| `pip_speaker` | The visual fills the frame; the speaker keeps talking in a small bubble (circle or rounded rectangle) in a bottom corner. | Detail-heavy visuals that need the full width: screen recordings, product UI, maps, long b-roll, step-by-step demos. The voice continues, so the face stays as a small anchor. |
| `cutaway` | B-roll or an AI clip fills the frame; the speaker is hidden but the voice runs underneath. | A concrete noun or action being described ("pouring the milk", "the grinder"). 1.5–4 s. |
| `speaker_cutout` | The speaker, cut out from the background (remove-background), stands in front of the graphic or a branded field. | Presenter-led explainers, intros and section openers. Needs a clean matte; check edges in QA. |
| `text_full` | Full-screen kinetic type, no speaker. | The hook card, chapter titles, the one line to remember. 1–3 s. |

Landscape (16:9) adds `side_by_side`: the speaker on the left third, the visual on the right two-thirds. Use it for tutorials and long-form explainers.

## Choosing a layout for each beat

Go through the story sections and transcript beats in order. For each beat, ask:

1. **What does the beat carry?**
   - A feeling or an opinion → `full_speaker`.
   - A keyword or a number → `speaker_overlay`.
   - A relationship or a trend → `split`.
   - Something to see in detail → `pip_speaker`.
   - A thing or an action → `cutaway`.
   - A title or a chapter → `text_full` or `speaker_cutout`.
2. **How long is it?** An overlay lasts at most 3 s. A split or PiP lasts at least 4 s (shorter ones read as flicker). A cutaway runs 1.5–5 s; `text_full` runs at most 3 s.
3. **Does the face matter right now?** If the speaker is reacting, joking or stressing, keep the face large: use `split` or `speaker_overlay`, not `pip_speaker` or `cutaway`.
4. **Does the visual need the full width?** UI, maps, small text and wide footage do. Use `pip_speaker` or `cutaway`, never a half-height split.
5. **Where are the keep-outs?** Overlays go in free space outside the face and burned-in text boxes. If there is no free space, escalate: overlay → split → PiP.
6. **What do the direction sheet and the dials say?**
   - Density 1–3 favours `full_speaker` and `speaker_overlay`.
   - Density 7 or more favours `split`, `pip_speaker` and `side_by_side`.
   - The sheet's `layouts:` list gives the direction's preferred kinds. Prefer those, but the content of the beat wins.
7. **Does the brand forbid something?** Follow `brands.<b>.visual.dont`, for example "never hide the presenter". That rule is enforced as a minimum speaker-visible share.

## Variety and continuity rules

- **Speaker presence.** In talking-head profiles the speaker is visible (any kind except `cutaway` and `text_full`) for at least 70% of the runtime. A long stretch without the face loses the person viewers came for.
- **Variety.**
  - Use at least 3 distinct kinds per 60 s when density is 4 or more.
  - Never use the same non-default kind 3 times in a row. Returns to `full_speaker` between them don't count as a break, and a run of beats in one layout counts as one entry.
  - Keep consecutive graphics in one open split rather than closing and reopening it (motion-recipes § split-screen).
- **Smooth handoffs.** Every layout change is a transition of at least the taste minimum (`derived.layout_transition_min_s`, usually 0.6 s) with an in-out ease. The speaker's face never jumps in size between kinds: animate scale and position, don't cut them, unless it is a hard cut on a footage cut.
- **Captions follow the head** in every kind:
  - `pip_speaker`: captions sit above the bubble, in the lower third of the visual, never inside the bubble.
  - `cutaway` and `text_full`: captions stay in the caption band.
- **Safe zones.** A PiP bubble sits inside the safe zone and never under the right rail. "Bottom" means the bottom of the safe zone, not of the frame. On Reels the bubble must end at or above y = 1250, because the caption, username and audio UI sit below it; a 320 px bubble at `[70, 900, 320, 320]` fits. The left side is usually the safest because the right rail holds the like and share buttons. Its diameter is 260–420 px on a 1080-wide canvas.

## Recipes

- `full_speaker` + camera: motion-recipes § camera-rig.
- `speaker_overlay`: motion-recipes § card-entrance and § kinetic-title, placed outside the keep-outs.
- `split`: motion-recipes § split-screen for graphics.
- `cutaway`: motion-recipes § ai-clip cutaway.
- `pip_speaker`: the full-frame visual sits underneath. The speaker is a muted copy of the cut master inside a masked wrapper (`border-radius:50%` or 32 px, a 6 px ring in the brand accent, a soft scrim behind it). Enter by scaling the full-frame speaker down into the corner: animate the wrapper's `clip-path` and transform together over at least 0.6 s with `power3.inOut`. Exit by the reverse. The audible voice stays on the main take. Snapshot the start, middle and end of every PiP window: the face must be centred in the bubble with the chin visible.
- `speaker_cutout`: run `/media-use` background removal on the cut master (offer the cost at checkpoint A if a paid model is needed). Layer it as cutout over graphic, add a soft contact shadow only if the direction allows shadows, and check edges in a 200% crop.
