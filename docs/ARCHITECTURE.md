# Architecture notes

## Runtime boundary

PyMOL 2.5 and 3.1 use different embedded Python runtimes. Importing PLIP or
OpenBabel into either process risks binary and dependency conflicts. The plugin
therefore exports immutable analysis inputs and starts one `QProcess` using the
dedicated `pymol-plip-plugin` environment. Communication is newline-delimited
JSON; no PLIP object crosses the process boundary.

The worker requires exactly PLIP 3.0.1 and OpenBabel 3.2.1 or newer and reports
its Python and engine versions before analysis. Startup never mutates any
environment.

```mermaid
flowchart LR
    A["PyMOL receptor + multi-state ligand"] --> B["Immutable per-state PDB export"]
    B --> C["External PLIP worker"]
    C --> D{"Per-pose cache hit?"}
    D -->|yes| E["Versioned normalized profile"]
    D -->|no| F["PLIP analysis"]
    F --> E
    E --> G["Nine state-aligned CGO objects"]
    G --> H["Native PyMOL state arrows"]
```

## Export contract

- The receptor state is frozen when analysis starts.
- The default effective selection is `(user receptor) and
  (polymer.protein or solvent or inorganic)`.
- Ligand coordinates, elements, formal charges, explicit hydrogens, and integer
  bond orders are reconstructed from `cmd.get_model` without touching the
  source object.
- Each requested pose is assigned a collision-checked synthetic `LIG` residue
  identity. The worker retains only that exact PLIP binding-site key, so
  unrelated cofactors in the receptor cannot leak into the requested profile.
- Input hydrogens are used only when both partners contain them. Otherwise PLIP
  adds missing polar hydrogens. The choice is stored in the profile and cache
  key.

PDB is used only as PLIP's process-boundary input. The loaded PyMOL chemistry is
the authoritative source; the supplied PLIP 2.4 XML/PSE files are presentation
references, not count fixtures.

## Profile schema

Each profile records:

- schema version, compound title, receptor and pose hashes;
- PLIP, OpenBabel, and Python versions;
- hydrogen policy and captured diagnostics;
- interacting receptor residues;
- typed edges with start/end coordinates and class-specific metadata.

The canonical classes are `hydrogen_bonds`, `hydrophobic_contacts`,
`halogen_bonds`, `water_bridges`, `salt_bridges`,
`pi_stacking_parallel`, `pi_stacking_t`, `pi_cation`, and
`metal_coordination`. A water bridge is represented by two connected edges so
the water position remains visible in the CGO geometry.

## Cache

The default macOS location is
`~/Library/Caches/PLIPPoseInspector`. Entries are gzip-compressed JSON and are
written atomically. Cache keys include:

- cache and profile schema versions;
- PLIP, OpenBabel, and worker Python versions;
- receptor atoms/connectivity and selected receptor expression/state;
- ligand atoms, coordinates, connectivity, formal charges, and hydrogens;
- target synthetic residue identity and hydrogen policy.

Changing any of these inputs causes an independent miss. Successful poses are
cached even when another state fails or the later run is cancelled.

## Rendering and ownership

One CGO object is created per interaction class. Every object receives exactly
the ligand's state count, including an explicit empty CGO for missing or failed
states. This prevents a previous state's contacts from remaining visible and
lets PyMOL synchronize geometry natively without analysis or redraw callbacks.

All names begin with `PLIP_Pose_Inspector_` and live under a run group with
`Interactions` and `Structures` subgroups. Only these names are ever deleted.
The optional pocket is a disposable copy of current interacting receptor
residues; the original receptor and ligand representations remain unchanged.

The 175 ms state watcher updates only dialog text/counts and this optional
pocket. Closing the dialog does not destroy the controller or watcher.

## Failure and cancellation semantics

The current overlay stays intact while a worker runs. On partial completion,
successful state profiles render with explicit empty states for failures and
the UI reports each failed pose. Cancelling kills the worker, discards pending
UI results, preserves the previous overlay, and leaves already completed cache
entries available for the next run.
