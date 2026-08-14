# Beta feedback notes

## Gate 1 — five-pose EP4 presentation

Status: Beta 0.2 ready for user retest after opening `demos/EP4_first5_beta.pse` or
running `@demos/ep4_first5.pml`.

Please review:

- Are the line colors easy to distinguish on your usual background?
- Do the native solid/dashed styles and `.09` demo radius read clearly?
- Do **Current pose** and **All analyzed poses** cover the desired pocket
  workflows?
- Are the object selectors, interaction toggles, counts, and progress display
  comfortable for routine compound triage?
- Does state switching feel immediate with all and individual classes enabled?

Feedback log:

- 2026-08-14: Beta 0.1 passed basic loading and state switching with no
  perceptible delay. Colors and the compact overall menu were accepted.
- 2026-08-14: reported a missing THR A/76 pocket residue after reopening the
  demo, fixed-radius CGO dashes that ignored `dash_radius`, ambiguous action
  labels, and overlapping Current Pose/Profile text.
- 2026-08-14: Beta 0.2 replaced CGOs with native measurements, made the pocket
  PSE-safe and state-aligned, added current/union/hidden modes, renamed and
  explained the actions, and separated the status rows. Awaiting user retest.

## Gate 2 — 118-pose EP4 performance

Internal validation is complete; user workflow feedback remains gated on Gate
1. Results on the local Apple Silicon machine:

- 118/118 profiles succeeded; no per-state failures.
- PyMOL 2.5: 28.5 seconds cold and 3.9 seconds warm, with approximately 91 MB
  peak process RSS.
- PyMOL 3.1: 28.0 seconds cold and 3.8 seconds warm, with approximately 122 MB
  peak process RSS.
- Warm runs had 118 cache hits; their timing includes rebuilding native
  measurement and pocket objects.
- All nine interaction objects contained 118 states.
- Cancellation after starting a full run preserved the prior analyzed profile
  and all 118 states of its existing overlay.

The remaining Gate 2 task is compound-triage feedback after Gate 1 presentation
choices are accepted.

## Gate 3 — CAU/2RH1 visual comparison

Internal analysis passes; final presentation feedback remains pending Gate 2.
Against `fixtures/2rh1/2RH1_CAU_A_408.pse`, live PLIP 3.0.1 found seven hydrophobic contacts,
three hydrogen bonds, and one T-shaped pi stack. The PLIP 2.4 XML contains the
same hydrophobic and pi-stacking counts and four hydrogen bonds. This expected
modern-engine/loaded-chemistry difference is not treated as a failure.

The final review should focus on interaction placement, colors, side-chain
pocket presentation, and the routine compound-selection workflow.
