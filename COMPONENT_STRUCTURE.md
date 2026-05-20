# Component Structure: When to Extract, When to Leave Alone

> Companion to `TEARDOWN.md`. The reviews told you *what* this repo should split. This doc covers *when and why* to split anything at all — generalizable past this codebase.

## The two failure modes

You're never choosing between "perfect" and "broken." You're choosing between two ways code rots:

**One Big File** — what this repo has.
- `dashboard.html` is 17,000 lines, one global namespace, no boundaries.
- Every change risks every other feature.
- Refactor tools can't tell what's load-bearing (this is exactly why our 13 declarations got pruned).
- New devs need weeks to know what's safe to touch.

**Death by 1000 Components** — the overcorrection.
- Every `<div>` is its own file.
- You need a map to find anything.
- Changing one feature touches 12 files because the seams went in the wrong places.
- Tests pass individually but the integrated system has subtle bugs no one can locate.

Neither is the goal. The goal is **boundaries in the right places**.

---

## What a component actually is

A component is a **promise**:

> "I can change anything inside this boundary without touching anything outside it."

If you can't keep that promise, the extraction made things worse. Reuse is one reason to extract — but only one. The bigger reasons are isolation (changes don't cascade), testability (you can test the piece without the whole app), and namability (you can describe what it does in one sentence).

If extraction doesn't buy you isolation, testability, or namability, you've just rearranged code.

---

## When extraction PAYS — five heuristics

### 1. The change-rate test (the most important one)

If two pieces of code **always change at the same time**, they belong together. If they **change for different reasons**, separate them.

Concrete example from this repo:
- The Competitors view changes when competitor logic changes.
- The Sources view changes when source-attribution changes.
- They never change at the same time, for the same reason.

→ They are different components. Extract.

Counter-example:
- The Overview view has a daily-trend chart and a per-provider chart.
- Both change together when `_AIM_SNAPSHOT` schema changes.
- Both change together when the design system changes.

→ They are **not** separate components. Keep them in one Overview module.

This is just **SRP applied to files**: a file should have one reason to change.

### 2. Rule of three — with a caveat

Three uses of the same shape = candidate for extraction. **But:** "same shape" ≠ "same concept."

- Two buttons that look identical but mean "save my work" and "delete my account" are NOT the same component. Their visual similarity is incidental; their *contracts* are different.
- Three modals that all need the same z-index, animation, and dismiss behavior **are** the same component, even if their contents differ.

Test for it: if requirements diverge in 6 months ("the delete button should turn red and require a confirmation"), do the use-sites still belong together? If yes → real component. If no → coincidental similarity.

### 3. The blast-radius test

When you edit this section, what else might break?

- Blast radius = "this 50-line section only" → fine, leave it inline.
- Blast radius = "the whole 17K-line file" → extract until the radius shrinks.

This test is how you can tell when *not* extracting becomes the bigger risk.

### 4. The "second pair of eyes" test

Could someone unfamiliar with the codebase understand what this section does without reading 500 lines of surrounding context?

- If yes → it has a real, nameable identity. Maybe extract.
- If no → it's tangled with its context. Either extract *and clarify* (worth it) or leave it alone (also fine).

The act of *naming* something forces clarity. If you can't name the extracted piece in 3 words, the piece you're extracting isn't real.

### 5. The testability test

Can you write a unit test for this without booting the whole app?

If no, you have implicit coupling — the piece "needs" things it doesn't ask for. Extract until you can write the test. This is the test the architect's TDD plan (`REVIEW_ARCHITECTURE.md` §4) is built on.

---

## When extraction COSTS more than it saves — four anti-patterns

### 1. The component-for-one
Extracting `<UserAvatar>` when you have exactly one user in exactly one place. You added a file, an import, and indirection. You got nothing back. **YAGNI.**

### 2. Props soup
The component takes 12 props, half of which are booleans toggling behavior. `<Button primary danger small loading disabled icon iconPosition="left" tooltip="..." href="..." onClick={...} />`. You haven't extracted a component; you've made a config object pretending to be UI. The variants should usually be separate components, or the component should be simpler.

### 3. The context leak
A component needs to know about its parent's parent's state to do its job. It's not a component, it's a tentacle. The parent should pass what's needed *explicitly* via parameters. If the parameter list becomes huge, see "props soup" above — the boundary is wrong.

### 4. The premature reusable
"We might need this elsewhere later." Don't extract for hypotheticals. Extract when the **second real use** appears. Building reusability for imaginary future users almost always produces APIs that none of the real future users actually want.

---

## Worked example: this repo's 7 views

`dashboard.html` has 7 views: Overview, Competitors, Prompts, Sources, Sentiment, Action Plan, Integrations.

Apply the change-rate test:

| View | Changes when… | Independent of others? |
|---|---|---|
| Overview | `_AIM_SNAPSHOT` top-level metrics shape changes | Mostly |
| Competitors | competitor scoring or comp-entity logic changes | Yes |
| Prompts | per-prompt metric shape changes | Yes |
| Sources | source attribution / domain logic changes | Yes |
| Sentiment | sentiment classifier changes | Yes |
| Action Plan | the 17 hard-coded action rules change | Yes |
| Integrations | API doc / key-gen logic changes | Yes |

→ These are 7 real components. The architect's plan to extract `src/views/*.js` (one per view, see `REVIEW_ARCHITECTURE.md` §3) matches this analysis exactly.

But now apply the test inside the Overview view:

| Sub-piece | Changes when… |
|---|---|
| Visibility score card | snapshot shape changes |
| Daily trend chart | snapshot shape changes |
| Sentiment breakdown | snapshot shape changes |
| Recent chats list | snapshot shape changes |

→ Everything in Overview changes for the same reason. **These are not separate components.** One Overview module is correct. Splitting each chart into its own file would just spread one change across 4 files.

This is the principle: **extract where work actually divides, not at every visual seam.**

---

## The two-question decision rule (use this when in doubt)

Before extracting anything, ask:

1. **Can I name what this piece does in one sentence using only its own vocabulary** (no "and also" / "except when" / "but the parent handles")?
2. **In the next 6 months, does this piece change for different reasons than the code around it?**

| Q1 | Q2 | Decision |
|---|---|---|
| Yes | Yes | Extract |
| Yes | No | Leave inline, but the name in your head is the function name |
| No | Yes | You have a hidden boundary — find it first, then extract |
| No | No | Leave it alone. Extraction would hurt. |

---

## The bottom line for a junior dev

You're not extracting **for reuse**. You're extracting **for independence**.

- A component is a promise that change inside the boundary doesn't escape it.
- Three uses is a hint, not a rule.
- The right question is never "could this be a component?" but "what changes together, and what changes for different reasons?"
- When tempted to extract "in case we need it later" — stop. Wait for the second real use.
- When tempted to leave it inline because "extraction is more code" — apply the blast-radius test. If editing this risks breaking unrelated things, you've already paid the cost of not extracting.

## The big mistake to avoid

Both failure modes — one giant file, and a thousand tiny files — come from the **same root cause**: people draw the boundaries somewhere other than where the work actually divides.

- Giant-file devs say "we'll figure boundaries out later" → never do.
- Death-by-1000-components devs say "every visual element is a boundary" → boundaries aren't visual, they're conceptual.

The work this repo needs (per the two reviews) isn't to chop `dashboard.html` into 200 files. It's to find the 4–6 places where things genuinely change for different reasons, and put boundaries there. That's it.

---

## How this fits with the rest of this branch

- `README.md` → "Debugging log": the incident that prompted this whole exercise.
- `TEARDOWN.md`: top-level synthesis with ranked ROI list.
- `REVIEW_ARCHITECTURE.md`: where the 6 actual boundaries live for this repo.
- `REVIEW_FRONTEND.md`: frontend-specific issues those boundaries help solve.
- **`COMPONENT_STRUCTURE.md` (this file)**: the *rules* the other docs apply.
