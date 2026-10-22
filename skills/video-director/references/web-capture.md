# Web capture with Playwright

The director uses the **playwright-cli** skill to read and record websites. It is the right tool when a video needs any of these:

1. **The client's brand, read from their website:** logo, colours, fonts, tone, handles.
2. **Real UI or site footage:** a product flow, a sign-up, a dashboard tour. This is footage for `pip_speaker`, `cutaway`, `cursor-demo` and `device-showcase`.
3. **Screenshots** of pages, articles, posts or reviews, for b-roll and UI fragments.

**Install (once):**

```bash
npm install -g @playwright/cli@latest
```
```bash
playwright-cli install --skills
```

You can also install the skill with `npx skills add microsoft/playwright-cli`. Read `/playwright-cli` before the first use; the commands below are the ones this skill relies on.

**Rules.** Only open sites the user named or that belong to the client. Decline non-essential cookie banners. Never sign in, type personal data or record logged-in personal pages unless the user set up the session for that purpose. Keep every capture inside the workspace, under `projects/<job>/assets/web/`.

## 1. Brand from a website

```bash
playwright-cli open
playwright-cli goto <url>
playwright-cli screenshot --hires --filename=projects/<job>/assets/web/home.png
playwright-cli --raw eval "JSON.stringify((()=>{const cs=e=>e&&getComputedStyle(e);const b=cs(document.body),h=cs(document.querySelector('h1,h2')),btn=cs(document.querySelector('a[class*=btn],button,[class*=button]'));const vars=[...document.styleSheets].flatMap(s=>{try{return [...s.cssRules]}catch(e){return []}}).filter(r=>r.selectorText===':root').map(r=>r.cssText).join(' ').match(/--[\w-]+:\s*#[0-9a-fA-F]{3,8}/g)||[];const logo=[...document.querySelectorAll('header img,header svg,img,link[rel*=icon]')].find(e=>/logo/i.test(e.outerHTML))||document.querySelector('link[rel*=icon]');return {title:document.title,description:document.querySelector('meta[name=description]')?.content,bodyFont:b.fontFamily,headingFont:h?.fontFamily,text:b.color,bg:b.backgroundColor,button:btn?.backgroundColor,cssVars:vars.slice(0,20),logo:logo?.src||logo?.href||null,social:[...document.querySelectorAll('a[href*=instagram],a[href*=tiktok],a[href*=youtube]')].map(a=>a.href)}})())"
playwright-cli close
```

Then:

- Download the logo URL into `brands/<slug>/`. If it is an inline `<svg>`, take its `outerHTML` with `eval` and save it as a file.
- Read the page text for tone of voice and the CTA wording.
- Run:

  ```bash
  python "$SKILL_DIR/scripts/brand.py" import brands/<slug> --id <slug> --client "<name>" --url <url> --set palette.primary=#… --set fonts.display="…"
  ```

Show what you inferred at checkpoint A and flag it as "read from the website, please confirm".

## 2. Recording UI or site footage

Plan the flow as steps in `edit-plan.yaml` first, as a `broll` item with `kind: web_capture`, its `url` and its `steps`. Then record it at the canvas aspect ratio:

```bash
playwright-cli open
playwright-cli resize 540 960                # 9:16 (1080x1920 at 2x); use 1280 720 for 16:9
playwright-cli goto <url>
playwright-cli video-start projects/<job>/assets/web/flow.webm --cursor --fps=60
playwright-cli video-chapter "Step 1" --duration=800
playwright-cli snapshot                      # find refs, then click / fill / scroll as planned
playwright-cli video-stop
playwright-cli close
```

- Pace the actions to the voiceover: about one action per spoken step, with each `--duration` matched to the speech.
- Convert the recording for HyperFrames:

  ```bash
  ffmpeg -i flow.webm -c:v libx264 -pix_fmt yuv420p -r 30 flow.mp4
  ```

- In the plan, the camera follows the cursor to each action (`cursor-demo`, `camera-cursor-tracking` in the motion library). The speaker sits in a `pip_speaker` bubble.
- Use real interfaces only. No fake dashboards; seed demo data the user approved.

## 3. Screenshots for b-roll

```bash
playwright-cli screenshot e12 --hires --filename=projects/<job>/assets/web/review.png   # one element
playwright-cli screenshot --hires --filename=...                                        # the viewport
```

- Crop element screenshots into UI fragments for `device-showcase` or `callout-arrow`.
- Give full-page captures a `ken-burns-still` or a scroll move.
- Credit third-party pages in `post.md` when they appear on screen.

## Choosing between this and HyperFrames capture

`npx hyperframes capture <url>` (see `/hyperframes-cli`) turns a website into a video project automatically. Use it when the whole video is a site tour. Use Playwright when you need control: a scripted flow, a specific element, logged-in UI the user set up, or reading the brand.
