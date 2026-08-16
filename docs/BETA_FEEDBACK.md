# Beta feedback

## Gate 1 — five-pose EP4 workflow

Open the supplied PLIP demo and Ligand Review Panel with
`@demos/ep4_first5.pml`.

Please review:

- depiction size, bond/stereo presentation, and compound-title readability;
- whether the floating window sits comfortably beside the PyMOL 3D view;
- synchronization using both PyMOL arrows and Previous/Next;
- Name/Identifier editing and Mark/Unmark behavior;
- Selected Compounds review, jump-to-pose, and CSV contents.

## Gate 2 — 118-pose triage

Internal validation produced 118/118 depictions with no failures and confirmed
every canonical SMILES against direct RDKit reads in PyMOL 3.1:

- PyMOL 2.5: 2.8 seconds cold, 1.6 seconds warm, approximately 71 MiB peak
  PyMOL-process RSS.
- PyMOL 3.1: 2.1 seconds cold, 1.2 seconds warm, approximately 103 MiB peak
  PyMOL-process RSS.
- Cancellation retained completed results, and state switching invoked no
  worker after precomputation.

User feedback should focus on prolonged compound-triage ergonomics and whether
additional keyboard shortcuts or metadata fields would help.
