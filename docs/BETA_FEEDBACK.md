# Beta feedback notes

## Gate 1 — five-pose EP4 presentation

Status: Beta 0.5 ready for user retest after opening `demos/EP4_first5_beta.pse` or
running `@demos/ep4_first5.pml`.

Please review:

- Are the line colors easy to distinguish on your usual background?
- Do the native solid/dashed styles and `.09` demo radius read clearly?
- Do **Current pose** and **All analyzed poses** cover the desired pocket
  workflows?
- Are the object selectors, interaction toggles, counts, and progress display
  comfortable for routine compound triage?
- Does state switching feel immediate with all and individual classes enabled?
- Does the detachable 2D structure remain readable beside your usual PyMOL
  window, and do Name/Identifier editing and marking fit your triage rhythm?
- Does the selected-compound table and CSV contain the traceability needed for
  purchasing or downstream prioritization?

Feedback log:

- 2026-08-14: Beta 0.1 passed basic loading and state switching with no
  perceptible delay. Colors and the compact overall menu were accepted.
- 2026-08-14: reported a missing THR A/76 pocket residue after reopening the
  demo, fixed-radius CGO dashes that ignored `dash_radius`, ambiguous action
  labels, and overlapping Current Pose/Profile text.
- 2026-08-14: Beta 0.2 replaced CGOs with native measurements, made the pocket
  PSE-safe and state-aligned, added current/union/hidden modes, renamed and
  explained the actions, and separated the status rows.
- 2026-08-14: Beta 0.2 retest confirmed correct state-specific residues,
  immediate live current/union/hidden switching, native radius control, and
  readable status rows. Reopening the supplied PSE exposed that its controller
  could not attach to saved pocket geometry. Requested user-facing colors and
  patterns, visible diagnostics, working citation information, and fixture
  housekeeping.
- 2026-08-14: Beta 0.3 prebuilds both pocket geometries, attaches to saved
  sessions without PLIP, persists hidden mode, adds scoped appearance defaults,
  diagnostics and Qt citation dialogs, and moves reference data under
  `fixtures/`. Awaiting user retest.
- 2026-08-16: Beta 0.4 adds the optional Ligand Review Panel launcher. Internal
  PyMOL 2.5/3.1 tests confirm the saved PLIP overlay and RDKit depiction follow
  the same state before and after the 2D window is hidden. Awaiting feedback on
  the combined 3D interaction/2D selection workflow.
- 2026-08-16: live testing found the 2D reviewer worked exceptionally well and
  requested one repository, installation, environment, and product. Beta 0.5
  renames the product PyMOL Pose Inspector, integrates the detachable reviewer,
  shares ligand/state/runtime settings, preserves legacy commands and caches,
  and retires the standalone ZIP.

## Gate 2 — 118-pose EP4 performance

Internal validation is complete; user workflow feedback remains gated on Gate
1. Results on the local Apple Silicon machine:

- 118/118 profiles succeeded; no per-state failures.
- PyMOL 2.5: 26.8 seconds cold and 2.5 seconds warm, with approximately 95 MiB
  peak process RSS.
- PyMOL 3.1: 25.4 seconds cold and 2.3 seconds warm, with approximately 129 MiB
  peak process RSS.
- Warm runs had 118 cache hits; their timing includes rebuilding native
  measurement and pocket objects.
- All nine interaction objects contained 118 states.
- Cancellation after starting a full run preserved the prior analyzed profile
  and all 118 states of its existing overlay.
- Fresh controllers changed and persisted pocket/appearance modes without
  launching the worker.

The remaining Gate 2 task is compound-triage feedback after Gate 1 presentation
choices are accepted.

Beta 0.5 adds a unified concurrent benchmark: PLIP profiles and RDKit
depictions are generated from one Python 3.12 environment in independent
processes, and both are checked against the same global PyMOL state.

## Gate 3 — CAU/2RH1 visual comparison

Internal analysis passes; final presentation feedback remains pending Gate 2.
Against `fixtures/2rh1/2RH1_CAU_A_408.pse`, live PLIP 3.0.1 found seven hydrophobic contacts,
three hydrogen bonds, and one T-shaped pi stack. The PLIP 2.4 XML contains the
same hydrophobic and pi-stacking counts and four hydrogen bonds. This expected
modern-engine/loaded-chemistry difference is not treated as a failure.

The final review should focus on interaction placement, colors, side-chain
pocket presentation, and the routine compound-selection workflow.
