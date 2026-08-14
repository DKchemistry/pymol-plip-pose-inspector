# Beta feedback notes

## Gate 1 — five-pose EP4 presentation

Status: ready for user beta after opening `demos/EP4_first5_beta.pse` or
running `@demos/ep4_first5.pml`.

Please review:

- Are the line colors easy to distinguish on your usual background?
- Do solid versus dashed/rounded styles communicate the classes clearly?
- Is the interacting-residue pocket useful, and is sticks-only the right
  default presentation?
- Are the object selectors, interaction toggles, counts, and progress display
  comfortable for routine compound triage?
- Does state switching feel immediate with all and individual classes enabled?

Feedback log:

- 2026-08-14: initial implementation; awaiting beta feedback.

## Gate 2 — 118-pose EP4 performance

Internal validation is complete; user workflow feedback remains gated on Gate
1. Results on the local Apple Silicon machine:

- 118/118 profiles succeeded; no per-state failures.
- Cold run: 26.3 seconds, including eight within-run hits from duplicate
  chemistry/poses.
- Warm run: 0.61 seconds with 118 cache hits.
- Peak PyMOL-process RSS: approximately 98 MB.
- All nine interaction objects contained 118 states.
- 1,180 programmatic state changes took under one millisecond before GUI
  redraw.
- Cancellation after starting a full run preserved the prior analyzed profile
  and all 118 states of its existing overlay.

The remaining Gate 2 task is compound-triage feedback after Gate 1 presentation
choices are accepted.

## Gate 3 — CAU/2RH1 visual comparison

Internal analysis passes; final presentation feedback remains pending Gate 2.
Against `2RH1_CAU_A_408.pse`, live PLIP 3.0.1 found seven hydrophobic contacts,
three hydrogen bonds, and one T-shaped pi stack. The PLIP 2.4 XML contains the
same hydrophobic and pi-stacking counts and four hydrogen bonds. This expected
modern-engine/loaded-chemistry difference is not treated as a failure.

The final review should focus on interaction placement, colors, side-chain
pocket presentation, and the routine compound-selection workflow.
