#!/usr/bin/env python
"""
Rosetta interface ddG for one nanobody-target complex (PyRosetta).

Standalone adaptation of scripts/scoring/minterface.py:
  - takes a single complex PDB (chains H + T for a nanobody)
  - loads the *shipped* util_minterface.xml (not the hardcoded /net path)
  - minimises the interface, then computes the nanobody interface ddG
    (+ Fv net charge and SAP score where available)
  - prints one line:  ddg=<kcal/mol>|fv_charge=<e>|sap_score=<au>

Run this with the python from your PyRosetta env, e.g.
    /path/to/pyrosetta-env/bin/python scripts/biosensor/score_rosetta.py complex.pdb
select_designs.py calls it per surviving design (see --rosetta-cmd).

Requires PyRosetta (academic licence). It is NOT in the GPU env on purpose —
install it in a separate environment (see scripts/biosensor/README.md).
"""
import argparse
import os
import sys

from pyrosetta import Pose, init
from pyrosetta.rosetta import core, protocols, rosetta

DEFAULT_XML = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "scoring", "util_minterface.xml")


def rechain_pose(pose, chainorder):
    """Reorder chains to `chainorder`, preserving residue labels (from minterface.py)."""
    splits = pose.split_by_chain()
    if all(splits[i].pdb_info().chain(1) == chainorder[i - 1]
           for i in range(1, len(splits) + 1)):
        return pose
    if len(splits) != len(chainorder):
        raise Exception(f"Pose has {len(splits)} chains, expected {len(chainorder)}")
    retpose = None
    for chain in chainorder:
        for subchain in splits:
            if subchain.pdb_info().chain(1) == chain:
                if retpose is None:
                    retpose = subchain
                else:
                    retpose.append_pose_by_jump(subchain, retpose.total_residue())
    pdbinfo = core.pose.PDBInfo(retpose)
    for resi in range(1, retpose.total_residue() + 1):
        pdbinfo.set_resinfo(resi, retpose.pdb_info().chain(resi), resi)
        labels = retpose.pdb_info().get_reslabels(resi)
        if len(labels) > 0:
            pdbinfo.add_reslabel(resi, labels[1])
    retpose.pdb_info(pdbinfo)
    return retpose


def calc_sap(pose):
    """SAP score on the antibody chains only (from minterface.py). Best-effort."""
    from pyrosetta.rosetta.core.pack.guidance_scoreterms.sap import calculate_sap
    tmppose = None
    for chain in pose.split_by_chain():
        if chain.pdb_info().chain(1) != "T":
            if tmppose is None:
                tmppose = chain
            else:
                tmppose.append_pose_by_jump(chain, tmppose.total_residue())
    sel = rosetta.core.select.residue_selector.TrueResidueSelector()
    return calculate_sap(tmppose, sel, sel, sel)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdb", help="complex PDB (nanobody chain H + target chain T)")
    ap.add_argument("--xml", default=DEFAULT_XML, help="util_minterface.xml path")
    args = ap.parse_args()

    init("-beta_nov16 -mute all")
    xml = protocols.rosetta_scripts.XmlObjects.create_from_file(args.xml)
    minterface = xml.get_mover("minimize_interface")
    nb_ddg = xml.get_filter("nb_ddg")
    ab_ddg = xml.get_filter("ab_ddg")
    fv_net_charge = xml.get_filter("fv_net_charge")
    if isinstance(nb_ddg, protocols.filters.StochasticFilter):
        nb_ddg = nb_ddg.subfilter()
    if isinstance(ab_ddg, protocols.filters.StochasticFilter):
        ab_ddg = ab_ddg.subfilter()
    if isinstance(fv_net_charge, protocols.filters.StochasticFilter):
        fv_net_charge = fv_net_charge.subfilter()

    pose = Pose()
    with open(args.pdb) as fh:
        rosetta.core.import_pose.pose_from_pdbstring(pose, fh.read())

    chains = {pose.pdb_info().chain(i) for i in range(1, pose.total_residue() + 1)}
    if "T" not in chains:
        sys.exit("ERROR: no chain T (target) in pose")
    if "H" in chains and "L" in chains:
        igtype, order = "ab", ["H", "L", "T"]
    elif "H" in chains:
        igtype, order = "nb", ["H", "T"]
    elif "L" in chains:
        igtype, order = "nb", ["L", "T"]
    else:
        sys.exit("ERROR: no H or L chain in pose")

    pose = rechain_pose(pose, order)
    minterface.apply(pose)
    ddg = (ab_ddg if igtype == "ab" else nb_ddg).compute(pose)

    try:
        fv_charge = fv_net_charge.compute(pose)
    except Exception:
        fv_charge = float("nan")
    try:
        sap = calc_sap(pose)
    except Exception:
        sap = float("nan")

    print(f"ddg={ddg}|fv_charge={fv_charge}|sap_score={sap}")


if __name__ == "__main__":
    main()
