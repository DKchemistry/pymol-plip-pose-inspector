# Changelog

## 0.4.0 — 2026-08-16

- Added an optional **2D Review…** launcher for the standalone Ligand Review
  Panel, bound to the current ligand object.
- Added the `plip_2d ligand=""` command and graceful guidance when the
  companion plugin is unavailable.
- Verified concurrent PLIP measurement overlays and state-synchronized RDKit
  depictions in PyMOL 2.5 and 3.1.

## 0.3.0 — 2026-08-14

- Prebuilt current-pose and all-analyzed pocket objects and changed modes using
  visibility only, eliminating recomputation after PSE reopening.
- Added saved-session discovery, attachment, hidden-mode persistence, and
  no-PLIP migration of Beta 0.2 pockets.
- Added per-class RGB colors, line-pattern presets, custom dash length/gap,
  project-local application, and persistent personal defaults.
- Added visible per-pose diagnostics and an automatic hydrogen-policy
  explanation.
- Replaced PyMOL's broken Pmw citation prompt with a first-use Qt dialog and
  permanent Citation action.
- Reorganized all CAU and EP4 reference material under `fixtures/`.
- Verified five and 118 poses, PSE persistence, appearance, cancellation, and
  CAU in PyMOL 2.5 and 3.1.

## 0.2.0 — 2026-08-14

- Replaced fixed-radius CGO contacts with state-aligned native PyMOL
  measurement objects. Global `dash_radius` now works normally.
- Replaced the timer-rebuilt pocket with a PSE-safe discrete molecular object.
- Added **Current pose**, **All analyzed poses**, and **Hidden** pocket modes,
  plus `plip_pocket` and `plip_analyze pocket=...` command support.
- Preserved cache compatibility and in-place replacement of Beta 0.1 overlays.
- Renamed **Analyze Current Only** and **Refresh Object Lists**, documented the
  latter, and refresh object menus whenever the dialog is shown.
- Separated Current Pose and Profile into full-width read-only status fields.
- Added cross-version measurement, dash inheritance, pocket, dialog geometry,
  current-only merge, 118-state, cancellation, and PSE persistence tests.

## 0.1.0 — 2026-08-14

- Initial Apple Silicon beta.
- External PLIP 3.0.1/OpenBabel 3.2.1 worker with health checking.
- Per-pose compressed persistent cache and cancellable asynchronous analysis.
- Nine independently toggleable, state-aligned CGO interaction classes.
- Optional current-pose interacting-residue pocket.
- Nonmodal Qt5 interface and four scriptable PyMOL commands.
- Verified with PyMOL 2.5.0 and 3.1.0, five-pose and 118-pose EP4 fixtures,
  PSE save/reopen, empty states, toggles, and cancellation.
