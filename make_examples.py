from pathlib import Path
from collections import defaultdict
import re

import gemmi
from rdkit import Chem


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

BASE_DIR = Path("/Users/lkv206/work/plip_plugin")

RECEPTOR_FILE = BASE_DIR / "ep4r_rec.crg.pdb"
LIGAND_FILE = BASE_DIR / "ep4r_matched_poses.sdf"
OUTPUT_DIR = BASE_DIR / "examples"

N_LIGANDS = 5

PROTEIN_CHAIN = "A"
LIGAND_CHAIN = "L"
LIGAND_RESNAME = "LIG"
LIGAND_RESNUM = 1


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def safe_filename(text: str) -> str:
    """Make a molecule name safe to use in a filename."""
    text = text.strip()
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text)
    return text or "ligand"


def ligand_atom_names(mol):
    """
    Generate unique PDB-style atom names such as:
        C1, C2, O1, N1, CL1, ...
    """
    counts = defaultdict(int)
    names = []

    for atom in mol.GetAtoms():
        element = atom.GetSymbol().upper()
        counts[element] += 1

        name = f"{element}{counts[element]}"

        if len(name) > 4:
            raise ValueError(
                f"Cannot represent atom name {name!r} in a 4-character "
                "PDB atom-name field."
            )

        names.append(name)

    return names


def make_ligand_chain(mol):
    """
    Convert an RDKit molecule with a 3D conformer into a Gemmi chain
    containing one HETATM residue named LIG.
    """
    if mol.GetNumConformers() == 0:
        raise ValueError("Ligand does not contain 3D coordinates.")

    conf = mol.GetConformer()
    atom_names = ligand_atom_names(mol)

    chain = gemmi.Chain(LIGAND_CHAIN)

    residue = gemmi.Residue()
    residue.name = LIGAND_RESNAME
    residue.seqid = gemmi.SeqId(LIGAND_RESNUM, " ")
    residue.het_flag = "H"
    residue.entity_type = gemmi.EntityType.NonPolymer

    for i, rd_atom in enumerate(mol.GetAtoms()):
        pos = conf.GetAtomPosition(i)

        atom = gemmi.Atom()
        atom.name = atom_names[i]
        atom.element = gemmi.Element(rd_atom.GetSymbol())

        atom.pos = gemmi.Position(
            float(pos.x),
            float(pos.y),
            float(pos.z),
        )

        atom.occ = 1.0
        atom.b_iso = 0.0

        # PDB supports integer formal charge, not partial charge.
        formal_charge = rd_atom.GetFormalCharge()
        if -9 <= formal_charge <= 9:
            atom.charge = formal_charge

        residue.add_atom(atom)

    chain.add_residue(residue)

    return chain


def prepare_receptor():
    """
    Read the receptor with Gemmi and retain only chain A.

    Returns a Gemmi Structure containing one model and only chain A.
    """
    structure = gemmi.read_structure(str(RECEPTOR_FILE))

    if len(structure) == 0:
        raise RuntimeError(
            f"No models found in receptor: {RECEPTOR_FILE}"
        )

    if len(structure) != 1:
        raise RuntimeError(
            f"Expected one model in receptor but found {len(structure)}."
        )

    model = structure[0]

    chain_names = [chain.name for chain in model]

    if PROTEIN_CHAIN not in chain_names:
        raise RuntimeError(
            f"Chain {PROTEIN_CHAIN!r} not found in receptor.\n"
            f"Available chains: {chain_names}"
        )

    # Remove everything except chain A.
    for chain_name in chain_names:
        if chain_name != PROTEIN_CHAIN:
            model.remove_chain(chain_name)

    # We will generate our own ligand connectivity.
    structure.clear_conect()

    return structure


def add_ligand_conect(structure, mol):
    """
    Add PDB CONECT records for ligand bonds.

    We deliberately record connectivity only, not bond order.
    Standard PDB CONECT records do not have a portable bond-order field.
    """
    model = structure[0]
    ligand_residue = model[LIGAND_CHAIN][0]
    ligand_atoms = list(ligand_residue)

    if len(ligand_atoms) != mol.GetNumAtoms():
        raise RuntimeError(
            "RDKit/Gemmi ligand atom counts do not agree."
        )

    for bond in mol.GetBonds():
        i = bond.GetBeginAtomIdx()
        j = bond.GetEndAtomIdx()

        structure.add_conect(
            ligand_atoms[i].serial,
            ligand_atoms[j].serial,
            order=1,
        )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not RECEPTOR_FILE.exists():
        raise FileNotFoundError(RECEPTOR_FILE)

    if not LIGAND_FILE.exists():
        raise FileNotFoundError(LIGAND_FILE)

    # Preserve explicit hydrogens from the SDF.
    supplier = Chem.SDMolSupplier(
        str(LIGAND_FILE),
        sanitize=True,
        removeHs=False,
        strictParsing=True,
    )

    if len(supplier) < N_LIGANDS:
        raise RuntimeError(
            f"Requested {N_LIGANDS} ligands, but SDF contains "
            f"only {len(supplier)} records."
        )

    structure = prepare_receptor()
    model = structure[0]

    protein_atoms = model[PROTEIN_CHAIN].count_atom_sites()

    print(f"Receptor: {RECEPTOR_FILE}")
    print(f"Retained chain: {PROTEIN_CHAIN}")
    print(f"Protein atoms: {protein_atoms}")
    print(f"Ligands: first {N_LIGANDS} records from {LIGAND_FILE}")
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    # Minimal produces essentially coordinate records rather than carrying
    # stale metadata for chains that we removed.
    pdb_options = gemmi.PdbWriteOptions(
        minimal=True,
        cryst1_record=False,
        numbered_ter=False,
        preserve_serial=True,
        conect_records=True,
        end_record=True,
    )

    written = []

    for index in range(N_LIGANDS):
        mol = supplier[index]

        if mol is None:
            raise RuntimeError(
                f"RDKit failed to parse SDF record {index + 1}."
            )

        if mol.GetNumConformers() == 0:
            raise RuntimeError(
                f"SDF record {index + 1} has no coordinates."
            )

        if mol.HasProp("_Name") and mol.GetProp("_Name").strip():
            ligand_name = mol.GetProp("_Name").strip().split()[0]
        else:
            ligand_name = f"ligand_{index + 1:02d}"

        # Add ligand as a new chain L.
        ligand_chain = make_ligand_chain(mol)
        model.add_chain(ligand_chain)

        # Assign unique PDB atom serial numbers across receptor + ligand.
        structure.assign_serial_numbers(numbered_ter=False)

        # Add ligand CONECT records using those newly assigned serials.
        structure.clear_conect()
        add_ligand_conect(structure, mol)

        output_file = (
            OUTPUT_DIR
            / f"{index + 1:02d}_{safe_filename(ligand_name)}.pdb"
        )

        structure.write_pdb(
            str(output_file),
            pdb_options,
        )

        written.append(output_file)

        print(
            f"{index + 1:02d}  "
            f"{ligand_name:<24} "
            f"{mol.GetNumAtoms():>3} ligand atoms  "
            f"-> {output_file.name}"
        )

        # Restore the receptor-only structure for the next ligand.
        model.remove_chain(LIGAND_CHAIN)
        structure.clear_conect()

    print()
    print(f"Done: wrote {len(written)} complexes.")

    for path in written:
        print(f"  {path}")


if __name__ == "__main__":
    main()