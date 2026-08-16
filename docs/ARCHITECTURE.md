# Architecture

## Runtime boundary

The PyMOL process owns only Qt widgets, state observation, immutable SDF
export, cached PNG loading, and the session worklist. One `QProcess` invokes
`worker.py` in an RDKit environment. Newline-delimited JSON streams health,
depictions, failures, progress, and completion back to the controller.

RDKit is never imported into PyMOL, even when the PyMOL interpreter happens to
provide it. This keeps PyMOL 2.5 and 3.1 behavior consistent and avoids binary
dependency conflicts.

## Export and depiction

The ligand selection must resolve to exactly one molecular object. PyMOL
exports every state independently as SDF without modifying the source. The
active state is first in the worker manifest, followed by the remaining states
in ascending order.

RDKit sanitizes each SDF record, assigns stereochemistry, removes explicit
hydrogens for standard medicinal-chemistry presentation, creates canonical
isomeric SMILES, computes canonical 2D coordinates, and draws a 600×400 Cairo
PNG. Invalid states fail independently and cannot be marked.

## Cache and synchronization

The platform cache key includes canonical isomeric SMILES, RDKit version,
depiction/cache schema versions, dimensions, and drawing settings. PNGs are
written with a same-directory temporary file followed by `os.replace`.

A 125 ms Qt timer observes PyMOL's global state. Once a record exists, state
changes only select metadata and load the cached path into `QPixmap`; no worker
call or molecular modification occurs.

## Selection identity

The stable compound key hashes the cleaned original state title and canonical
isomeric SMILES. Editable Name and Identifier are export metadata and do not
change this key. Matching `object:state` sources accumulate as records arrive.
The ordered worklist lives only in the plugin controller for the current PyMOL
process. CSV export uses a same-directory temporary file and atomic replace.

## Optional PLIP bridge

PLIP Pose Inspector dynamically imports `pymol_ligand_review` only when the
user presses **2D Review…** or calls `plip_2d`. The companion receives the
current ligand selection, then operates independently. A missing companion
produces installation guidance rather than a hard plugin dependency.

