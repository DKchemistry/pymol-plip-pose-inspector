# Changelog

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
