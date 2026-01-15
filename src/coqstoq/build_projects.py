import argparse
import subprocess
from pathlib import Path
from dataclasses import dataclass
from coqstoq.eval_thms import Project
from coqstoq.predefined_projects import (
    BB5,
    COMPCERT,
    PNVROCQLIB,
    PREDEFINED_PROJECTS,
)
import logging


@dataclass
class BuildInstructions:
    project: Project
    instrs: list[list[str]]


def routine_build(project: Project, n_jobs: int) -> BuildInstructions:
    return BuildInstructions(
        project,
        [["make", "-j", str(n_jobs)]],
    )


def compcert_build(n_jobs: int) -> BuildInstructions:
    configure = ["./configure", "x86_64-linux"]
    make_depend = ["make", "depend", "-j", str(n_jobs)]
    make_proof = ["make", "proof", "-j", str(n_jobs)]
    return BuildInstructions(
        COMPCERT,
        instrs=[configure, make_depend, make_proof],
    )


def pnv_build(n_jobs: int) -> BuildInstructions:
    coq_makefile = ["coq_makefile", "-f", "_CoqProject", "-o", "Makefile.coq"]
    make = ["make", "-f", "Makefile.coq", "-j", str(n_jobs)]
    return BuildInstructions(
        PNVROCQLIB,
        instrs=[coq_makefile, make],
    )


# Removed BB52 theorem.v; BB42 theorem.v; and BB25 theorem.v
MODIFIED_BB5_CP = """\
-Q . BusyCoq
BB52Statement.v
BB52.v
Finned1.v
Finned3.v
Finned5.v
FixedBin.v
Helper.v
Individual.v
Permute.v
ShiftOverflow.v
Skelet15.v
Skelet1.v
Skelet33.v
Skelet35.v
Compute.v
Finned2.v
Finned4.v
Finned.v
Flip.v
Individual52.v
LibTactics.v
ShiftOverflowBins.v
Skelet10.v
Skelet17.v
Skelet26.v
Skelet34.v
TM.v
"""


def bb5_build(n_jobs: int) -> BuildInstructions:
    with open(BB5.workspace / "_Custom_CoqProject", "w") as fout:
        fout.write(MODIFIED_BB5_CP)
    instrs = [
        ["coq_makefile", "-f", "_Custom_CoqProject", "-o", "CustomMakefile.coq"],
        ["make", "-f", "CustomMakefile.coq", "-j", str(n_jobs)],
    ]
    return BuildInstructions(BB5, instrs)


def run_build(instructions: BuildInstructions):
    print(f"Building {instructions.project.dir_name}...")
    if instructions.project.dir_name == "bb5":
        logging.warning(f"BB5 may take up to an hour to build.")
    for instr in instructions.instrs:
        result = subprocess.run(
            instr, cwd=instructions.project.workspace.resolve(), capture_output=True
        )
        if result.returncode != 0:
            build_instrs: str = "\n".join(" ".join(i) for i in instructions.instrs)
            print(
                f"Failed to build {instructions.project.dir_name}. To debug, run: {build_instrs}."
            )
            return
    print(f"Successfully built {instructions.project.dir_name}.")


def check_env() -> bool:
    """Could do more checks. For example versions etc."""
    try:
        subprocess.run(["coqc", "--version"], capture_output=True)
        return True
    except FileNotFoundError:
        logging.warning(
            "Please activate your opam switch. Run `opam switch` to see the current state."
        )
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Build CoqStoq projects on your machine.")
    parser.add_argument("--n_jobs", type=int, default=4)
    args = parser.parse_args()

    all_build_instrs: list[BuildInstructions] = []
    for p in PREDEFINED_PROJECTS:
        if p == COMPCERT:
            all_build_instrs.append(compcert_build(args.n_jobs))
        elif p == PNVROCQLIB:
            all_build_instrs.append(pnv_build(args.n_jobs))
        elif p == BB5:
            all_build_instrs.append(bb5_build(args.n_jobs))
        else:
            all_build_instrs.append(routine_build(p, args.n_jobs))

    for instr in all_build_instrs:
        run_build(instr)
