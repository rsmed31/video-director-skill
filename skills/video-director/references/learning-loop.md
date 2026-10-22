# Learning loop: feedback → rules

`director.yaml` (in the skill folder) is long-term memory shared by every workspace and job. `video-director.yaml` at a workspace root holds overrides for that folder only. All writes go through `scripts/director_memory.py`, so ids, dates and the schema stay consistent.

## What counts as feedback
- Anything the user says about a plan or a delivered video: complaints ("too slow"), wishes ("more zooms"), praise ("the captions are perfect"), corrections ("her name is Jane Doe").
- Changes they make at checkpoint A.
- Edits they make by hand in Studio, which you notice on resume. A diff against your last build is implicit feedback; ask once what it was about.
- Platform numbers they paste (skip rate, average watch time, saves, sends) go to `metrics` via `director_memory.py metric add`.
- Approval of a version (checkpoint B "looks good", or they post it) confirms every candidate rule that version applied.

## Turning a note into rules
1. **Log it verbatim:**
   `feedback add --job J --version vN --quote "..." [--items g-hook,b3]`
2. **Find the cause:** which plan items and rules produced what they're reacting to. The plan's `rules:` fields make this traceable.
3. **Generic or this client?** Brands are per client, and most notes are about one client's taste. Every feedback entry records `brand` and `applies`:
   - `generic`: how the user wants every video, whatever the client ("always show me key frames first", "never cover faces"). Scope `global`.
   - `client`: this client's taste or facts ("she wants calmer edits", "skin looks orange on her", "music louder for this channel"). Scope `brand:<client>`. Numbers go to `brands.<b>.profile_overrides.<key>` (`param set --path brands.<b>.profile_overrides.music_bed_db_under_voice --value "[-8,-6]"`).
   - `video`: this video only. Fix the plan; no rule.

   When the note doesn't make it clear, **ask the user**: "Is this for every client, or just for <client>?" Default to `client` when there is no answer. To move rules saved at the wrong scope, use `director_memory.py rescope --to brand:<b> --ids …` (or `--to global`).
4. **Choose the scope within that:** the narrowest that explains the note.
   - About this video only, e.g. "move that card": fix the plan. Add a rule only if it generalizes.
   - About the client, channel or style ("she prefers French titles"): `brand:<id>`.
   - About a content type ("talking heads need more b-roll"): `profile:<id>`.
   - About a platform ("captions hidden by the Instagram UI"): `platform:<id>`.
   - About how they like videos in general ("I always want SFX"): `global`.
5. **Write or adjust the rule:**
   - New idea: `rule add --scope S --text "..." --source user --evidence fb-NNNN`. It starts as `candidate`, confidence 0.6 (0.8 if the user stated it as a standing preference: "always", "never", "I want").
   - Agrees with an existing rule: `rule confirm --id R --evidence fb-NNNN`. Confidence +0.1; a candidate becomes default after 2 confirmations.
   - Contradicts an existing rule: `rule weaken --id R --evidence fb-NNNN`. Confidence −0.2. Don't delete it; below 0.3 it becomes `retired`. Tell the user about the conflict and ask which they want when it isn't obvious.
   - Absolute instruction ("never use glitch"): `ban --scope S --text "..." --evidence fb-NNNN`.
   - Numeric preference ("zoom less"): change the parameter in the profile or brand with `param set --path profiles.talking_head_edu.punch_in.normal --value "[1.05,1.12]" --evidence fb-NNNN`. Parameters are learned too.
6. **Apply now:** update the plan, rebuild, render a new version, and log in `job.yaml` what changed and which feedback ids drove it.

## Generalize the why, not the pixels
"The card covers my hand" is not "move cards 40 px left". It means "keep-out must include gesturing hands for this presenter": a brand rule plus a keep-out habit. "Wasn't animated enough" is not "add 3 more zooms". It means motion density and variety are below this user's taste: raise the profile's change cadence, add data-build-zoom and transitions, and log it as a standing preference.

## Confidence and status

| status | meaning | used how |
|---|---|---|
| `candidate` | plausible, not yet confirmed | apply, and mention it at checkpoint A ("trying X, based on your note on …") |
| `default` | confirmed or researched | apply silently |
| `ban` | hard constraint | never violate; plan_lint enforces the ones it can |
| `retired` | contradicted or obsolete | ignore; kept for history |

Research rules start at 0.45–0.7. A user's explicit standing preference starts at ≥0.8. Real metrics that support or contradict a rule move it by ±0.1 per job.

## When resolving for a job
`director_memory.py resolve --platform P --profile Q --brand B [--workspace .]` merges the layers (global → platform → profile → brand → workspace) and prints:
- the effective parameters;
- the active rules, sorted by confidence;
- the bans;
- the last 5 feedback entries for this brand or profile.

Read all of it before planning. The user should never have to repeat a note.

## Hygiene
- Run `director_memory.py validate` after edits (schema, duplicate ids, dangling evidence).
- Keep rule texts short and actionable. Put the reasoning in the feedback entry or the playbook, not in the rule.
- Every ~10 feedback entries, review the file: merge near-duplicate rules, retire stale ones, and tell the user what the director has learned.
