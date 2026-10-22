# Motion recipes (seek-safe, HyperFrames)

Patterns proven in real jobs. All of them animate on **one paused GSAP timeline** registered at `window.__timelines["<composition-id>"]`, and all are deterministic. Read `/hyperframes-core` and `/hyperframes-keyframes` for the contract. These are adaptations, not a replacement for those skills.

**Hard rules from the HyperFrames lint:**
- Animate children, never the timed `.clip` element itself, and don't use `visibility` or `autoAlpha` on clips.
- Never set a CSS `transform` on an element that GSAP also transforms. Put the start state in `fromTo`.
- Every `<audio>` and `<video>` needs an `id`.
- Named fonts need `@font-face` pointing to a local file.

Before hand-building, search the registry (`npx --yes hyperframes@<pin> catalog --query "<look>" --json`). Known useful items: `whip-pan-cut`, `zoom-through-transition`, `cinematic-zoom`, `flash-through-white`, `data-chart`, `animated-bar-chart`, `count-up`, `number-wheel`, `mk-specs-list`, `marker-checklist-card`, `caption-pill-karaoke`, `caption-highlight`, `hw-arrow`, `hw-callout-circle`, `lt-kicker-name`, `lt-dark-card`, `organic-light-leak-overlay`, `shimmer-sweep`, `comparison-split`. Many ship at 1920×1080; for vertical canvases, adapt their technique inline or wrap them in a scaled sub-composition.

## transition grammar (user feedback: "don't do fast transitions")
One grammar for the whole reel; declare it once at the top of the script and reuse it:
```js
const MOVE={duration:.9,ease:"power2.inOut"}, XF={duration:.5,ease:"sine.inOut"};
const IN={duration:.5,ease:"power2.out"},     OUT={duration:.4,ease:"power2.in"};
```
- Nothing under 0.4 s except caption pops (0.25 s, scale .94→1, power2.out). No `back.*`, `expo.*`, `power3.*` eases, no `rotationX` flips, no circle-reveal wipes.
- Punch-ins: 0.6 s power2.out, max 1.15; release 1.2 s sine.inOut. Source cuts stay hard cuts.
- Never crossfade two different shots of the same face (double-exposed ghost faces). Use a hard cut, or the vertical swipe below.
- Elements: card first, text +0.1 s; out before the next element comes in. No drop shadows; radii 28.
- QA: grep the composition for `back.out|expo|power3|duration: 0.[0-3]` and snapshot every transition at 0.1 s steps; no move may complete in fewer than 12 frames.

## photo open + seamless Reels loop
- Frame 0 and the last frame are the same full-bleed still (outpaint a non-9:16 photo with `scripts/outpaint_fill.py`; never blurred bars). Hook text fades in from 0.1 s over the still and fades out before the swipe.
- Photo ↔ footage = a vertical swipe (Reels-native), both layers moving together:
```js
root.fromTo("#intro",{y:0},{y:-1920,...MOVE},D);   root.fromTo("#cam",{y:1920},{y:0,...MOVE,immediateRender:false},D);
// the ending REUSES the intro layer (clip spans the whole root, hidden in between): a second <img> copy of the
// same still rendered ~7 levels darker/warmer than frame 0 in the real render (snapshots hid it)
root.set("#intro",{opacity:0},D+0.95);
root.set("#intro",{opacity:1},END); root.set("#photoIn",{scale:1.04},END);
root.fromTo("#intro",{y:1920},{y:0,...MOVE,immediateRender:false},END); root.fromTo("#cam",{y:0},{y:-1920,...MOVE,immediateRender:false},END);
```
- The outgoing hold frame must stay on screen until the swipe completes (extend the hold clip), or a black band appears.
- The still holds at the exact frame-0 scale for the last ~0.5 s. Verify on the RENDERED file, not snapshots: `frame_scan.py <render> --loop` must report a first/last frame difference < 1.
- Nest the main edit on its own timeline so a prepended intro does not shift every tween: `const tl=gsap.timeline(); root.add(tl, D)`; shift only `data-start` attributes (+D) and build captions with `build_captions.py --offset D`.

## camera-rig
Wrap all footage in one non-timed `#cam` div. Put cuts on the `<video>` clips inside it and animate only `#cam`.
```css
#cam { position:absolute; inset:0; transform-origin: 50% 35%; }   /* origin near the face, or near burned-in text you must keep in frame */
```
```js
tl.fromTo("#cam",{scale:1.1},{scale:1,duration:1.6,ease:"power3.out"},0);        // opening settle
tl.to("#cam",{scale:1.05,duration:6,ease:"sine.inOut"},2);                         // drift: never fully still
tl.set("#cam",{scale:1.14},12.75);                                                 // jump-cut mask (hard)
tl.to("#cam",{scale:1.25,duration:0.35,ease:"power3.out"},20.1);                   // emphasis punch on a key word
tl.to("#cam",{scale:1.06,duration:0.6,ease:"power2.inOut"},22.0);                  // release
```
- To aim a punch-in, animate `x`/`y` (or `xPercent`/`yPercent`) together with `scale`. Choose `transform-origin` per job from the keep-out map: the face when you want a close-up; the corner holding burned-in text when that text must stay in frame.
- Alternate tight and wide between sections. Return to 1.0 before section titles and outros.

## data-build-zoom (the "zoom into the graph" move)
A graphic panel builds up. The camera zooms *into the graphic* to the key value, holds, and pulls back out to the speaker.
```html
<div id="g-data" class="clip" data-start="30" data-duration="7" data-track-index="5">
  <div class="stage">                         <!-- this is what the zoom moves -->
    <div class="panel">
      <div class="bar b1"></div><div class="bar b2"></div><div class="bar b3 key"></div>
      <div class="val">0</div><svg class="arrow"><path d="..."/></svg>
    </div>
  </div>
</div>
```
```js
const s=30;
tl.fromTo("#g-data .panel",{y:120,opacity:0,scale:.9},{y:0,opacity:1,scale:1,duration:.5,ease:"back.out(1.4)"},s);
tl.fromTo("#g-data .bar",{scaleY:0},{scaleY:1,duration:.7,stagger:.15,ease:"power3.out",transformOrigin:"50% 100%"},s+.3);
const o={v:0}; tl.to(o,{v:82,duration:1.1,ease:"power2.out",onUpdate:()=>{document.querySelector("#g-data .val").textContent=Math.round(o.v)+"%"}},s+.6);
tl.fromTo("#g-data .arrow path",{strokeDasharray:400,strokeDashoffset:400},{strokeDashoffset:0,duration:.6},s+1.4);
// camera INTO the key bar: scale the stage around the key element's centre
tl.to("#g-data .stage",{scale:2.1,transformOrigin:"72% 40%",duration:.9,ease:"power3.inOut"},s+2.2);
tl.to("#g-data .stage",{scale:1,duration:.7,ease:"power3.inOut"},s+5.2);           // back out
tl.to("#g-data .panel",{y:80,opacity:0,duration:.35,ease:"power2.in"},s+6.6);
```
- `onUpdate` that writes text derived from the tween value is seek-safe: it is a pure function of time.
- Option: zoom the footage camera (`#cam`) *toward* the graphic panel while the panel scales up. This reads as one continuous camera move from the speaker into the data.
- SFX: whoosh-short on the panel entry, click-soft on each bar, sparkle or chime when the key value lands, whoosh on the zoom-in.

**Readability rules(the user rejected fast, abstract graphs and label overlaps):**
- One graph = one message. Reveal **one element per spoken beat** (time each to the word that names it), each >=0.5 s; total >=5 s when the speech allows.
- End on a plain-language **takeaway** box (>=40 px, dark pill) held >=1.5 s: "Too fine = bitter", "Timing changes everything". Labels >=32 px *after* any fit scaling.
- Never invent statistics: use qualitative labels ("balanced / over-extracted") unless the user gives numbers.
- Zoom slowly (1-1.2 s, `power2.inOut`, scale 1.15-1.25) and **anchor the zoom on the chart's bottom edge** (`transformOrigin: "88% 37.6%"` for a chart whose axis sits at canvas y~722) so content grows upward, away from the takeaway and captions. Fade axis labels just before the zoom.
- Place every label in empty space at the zoom peak too: two-line labels above a curve's end, start markers' labels under the curve, never across a line. Snapshot every zoom peak in QA.
- Round line caps show as dots before a path draws. Hide the path until its draw starts:
```js
const draw=(sel,t,dur,ease="power2.inOut")=>document.querySelectorAll(sel).forEach(p=>{const L=p.getTotalLength();
  tl.fromTo(p,{opacity:0},{opacity:1,duration:.01,immediateRender:true},t);
  tl.fromTo(p,{strokeDasharray:L,strokeDashoffset:L},{strokeDashoffset:0,duration:dur,ease},t);});
// restore a dashed style after drawing: tl.set(p,{strokeDasharray:"18 14",strokeDashoffset:0},t+dur)
```
- Never draw decorations (cracks, scribbles) across a word; put status marks (x / check) in their own badge on the card corner.

## section-slam (chapter change)
A full-width band wipes in with clip-path, a number and title stagger in, then the band wipes out. Pair it with a riser that **ends on the cut** and an impact on the cut.
```js
tl.fromTo("#ch2 .band",{clipPath:"inset(0 100% 0 0)"},{clipPath:"inset(0 0% 0 0)",duration:.32,ease:"power4.out"},t);
tl.fromTo("#ch2 .num",{x:-60,opacity:0},{x:0,opacity:1,duration:.35,ease:"back.out(2)"},t+.12);
tl.fromTo("#ch2 .ttl",{x:80,opacity:0},{x:0,opacity:1,duration:.4,ease:"power3.out"},t+.18);
tl.to("#ch2 .band",{clipPath:"inset(0 0% 0 100%)",duration:.3,ease:"power3.in"},t+1.25);
```
Keep the band inside the safe zone; on Reels that means y ≤ 1250 minus its height, not in the bottom UI area.

## whip / zoom-through transitions
- **Whip:** `#cam` `x: 0 → -1300` over 0.18 s (`power4.in`), add a short horizontal blur on an overlay (`filter: blur()` on a duplicate is costly, so prefer the registry `whip-pan-cut`), then hard-cut to the next shot entering from `x: 1300 → 0` (`power4.out`). SFX: whoosh-short centred on the cut.
- **Zoom-through:** scale `#cam` 1 → 2.4 (0.3 s `power3.in`) into a bright or dark area, cut, then the next shot goes 1.6 → 1 (0.4 s `power3.out`). Use the registry `zoom-through-transition` when going into a graphic card.
- Limit: `caps.whip_transition` per minute. Use them at section changes, not on every cut.

## kinetic-title
Text slabs reveal with a clip-path wipe, the accent word pops (`back.out(3)`), all slabs drift slightly while held, and they exit in a quick stagger. Time each line to the **spoken word** (word timings from the transcript), not to a round number.

## caption-pop (word-synced, RTL-safe)
- One `.cap.clip` per chunk on its own track: `data-start` = first word start, duration = last word end − start.
- Inner text is `dir="rtl"` for Arabic. Latin terms go in `<span class="lat" dir="ltr">` with `unicode-bidi: isolate`.
- Style: Cairo 900, ~66 px, cream fill with a 10 px ink stroke via `paint-order: stroke fill`, plus a soft shadow.
- Entry: `fromTo(inner,{scale:.7,y:22,opacity:0},{scale:1,y:0,opacity:1,duration:.22,ease:"back.out(2.6)"},start)`. Highlight keywords by tweening their color at `start + 0.12`.
- For karaoke-style per-word color, split into word spans and tween each at its own word start.
- Highlights: `.hl{display:inline-block;margin:0 .2em}` (inline spans neither scale nor keep their space in RTL); Latin spans `white-space:nowrap;display:inline-block` so a multi-word term never wraps mid-term.
- **Backing (Reels default):** `.in{display:inline-block;max-width:680px;padding:2px 22px 8px;border-radius:24px;background:rgba(27,23,20,.38)}` keeps captions readable over white clothing and graded footage and passes the contrast audit.

## captions-follow-head
Captions sit just under the speaker's chin, centred on the face, never in a fixed band that ignores the framing. Wrap every caption clip in one non-timed layer and move the layer with the layout:
```html
<div id="capLayer" style="position:absolute;inset:0;z-index:20"> <!--CAPTIONS:BEGIN--> ... <!--CAPTIONS:END--> </div>
```
```js
tl.to("#capLayer",{y:70,duration:.3,ease:"power2.out"},punchT);  tl.to("#capLayer",{y:0,duration:.1},punchEnd); // big punch-ins push the chin down
tl.to("#capLayer",{y:500,duration:.6,ease:"power3.inOut"},splitIn);  tl.to("#capLayer",{y:0,duration:.4},splitOut-.4); // split screen
```
Pick the offsets from snapshots (chin y per framing). Generate caption clips from `transcript.clean.json` with a small builder script so the transcript stays the source of truth.

## card-entrance (stills / PiP)
```js
tl.fromTo(`${id} .frame`,{y:90,opacity:0,rotation:-4,scale:.9},{y:0,opacity:1,rotation:0,scale:1,duration:.55,ease:"back.out(1.4)"},s);
tl.fromTo(`${id} .frame img`,{scale:1.16},{scale:1,duration:dur,ease:"none"},s);        // Ken Burns
tl.fromTo(`${id} .icon svg *`,{strokeDasharray:200,strokeDashoffset:200},{strokeDashoffset:0,duration:.9},s+.4); // line-draw icon
tl.to([`${id} .frame`,`${id} .label`],{y:50,opacity:0,duration:.35,stagger:.03,ease:"power2.in"},s+dur-.38);
```
Mark Ken Burns images `data-layout-allow-overflow` so the layout audit doesn't flag the intended overscan.

## split-screen for graphics (one of the layouts in references/layouts.md)
Full-width halves, **not a boxed card**: the graphic builds in the top half, the speaker's real footage fills the bottom half with the whole face visible, captions under the chin. The transition reads as "she slides down, the graph opens above".
```html
<!-- graphic: full-frame .gfx clip (bg + .stage > .fit + .take + .seam) under the speaker layer -->
<div id="pip"><div class="vw"><video id="take2" class="clip" data-layout-allow-overflow src="assets/cut.mp4"
     data-start="0" data-duration="<cut len>" data-media-start="0" muted playsinline></video></div></div>
```
```css
#pip{position:absolute;inset:0;z-index:11;opacity:0;clip-path:inset(0px 0px 0px 0px)}
#pip .vw,#pip video{position:absolute;left:0;top:0;width:1080px;height:1920px;object-fit:cover}
.gfx .fit{position:absolute;inset:0;transform:translate(0,-40px) scale(.8);transform-origin:50% 290px} /* squeeze graph into y 270-760 */
.take{top:756px;height:84px}  .seam{top:850px;height:10px;background:var(--teal)}
```
```js
[[a,b], ...].forEach(([a,b])=>{
  tl.fromTo("#pip",{opacity:0},{opacity:1,duration:.01,immediateRender:false},a);
  tl.fromTo("#pip",{clipPath:"inset(0px 0px 0px 0px)"},{clipPath:"inset(860px 0px 0px 0px)",duration:.6,ease:"power3.inOut",immediateRender:false},a);
  tl.fromTo("#pip .vw",{y:0},{y:480,duration:.6,ease:"power3.inOut",immediateRender:false},a);   // forehead lands on the seam
  tl.to("#pip",{clipPath:"inset(0px 0px 0px 0px)",duration:.4,ease:"power3.inOut"},b-.4);
  tl.to("#pip .vw",{y:0,duration:.4,ease:"power3.inOut"},b-.4);  tl.to("#pip",{opacity:0,duration:.01},b);
});
```
- The second `<video>` is a muted copy of the cut master (the audible one stays in `#cam`). Give it the same `data-color-grading` as `#take`.
- Tune `y` (480 here) so the forehead sits at the seam and the chin leaves room for captions; check every split window's frame, face positions differ per take.
- Raise SVG label sizes so they stay >=32 px after the `.fit` scale.
- **Continuity rules (critique-v7):** keep the split open across consecutive graphs and swap only the top graph (XF 0.45 s); the full-frame `#cam` must be at exactly scale 1.0 at every split start/end (ease it there 1 s before; no `set` within ±0.3 s of a handoff) or the face size jumps; make `#pip` opaque one frame before the split starts and draw the seam in (`scaleX 0→1`, 0.5 s, +0.45 s) so no teal line flashes over the face; start each split-out on a footage cut and extend the graph clip ~1 s so its background stays behind the expanding footage.
- A later take framed differently: on the hard cut, `tl.set("#pip .vw",{y:<offset>})` so the face sits in the bottom half before expanding.

## ai-clip cutaway
```html
<video id="ai-b2" class="clip" src="assets/ai/kettle-pour.mp4" data-start="41.2" data-duration="3.2"
       data-media-start="0.4" data-track-index="2" muted playsinline
       style="position:absolute;left:0;top:0;width:1080px;height:1920px;object-fit:cover"></video>
```
- Generated clips are b-roll, so keep them `muted`; the speaker's voice continues underneath.
- Enter with a hard cut, a zoom-through, or a split-panel slide. Trim the model's first 0.3–0.5 s, which is often static.

## progress-bar
A thin bar (8–10 px) inside the top safe edge, filled with `scaleX: 0 → 1` linear over the talk, with ticks at section starts. Fade it out before the outro.

## sfx-alignment
- Root-composition `<audio>` uses absolute `data-start`; inside a sub-composition it uses scene-local time.
- A riser of length L ending on the cut at T gets `data-start = T − L`. Bundled `riser` is 10.03 s, so trim it with `data-media-start` to its last ~1.5–2 s.
- Volumes: whoosh 0.3–0.45, pop 0.3–0.4, impact 0.35–0.5, sparkle or chime 0.3, all under the voice.
- No more than `caps.same_sfx_in_a_row` identical cues in a row; alternate `whoosh` and `whoosh-short`.

## music-bed
Build the bed offline with `scripts/music_bed.py` (voice-band EQ carve + light sidechain + fades, measured to land `--under` dB under the voice **during speech**), then place it as a plain full-length audio element:
`<audio id="bed" src="assets/music/bed_duck.wav" data-start="0" data-duration="<root>" data-volume="1">`.
- Level: 6-8 dB under the voice during speech. 18 dB under was inaudible on phones; 11 dB was still "not hearable at all" under continuous speech. Judge by `audio_backtest.py`, never by the bed's integrated LUFS.
- Ducking ratio <=1.6: hard ducking under nonstop speech buries the bed.
