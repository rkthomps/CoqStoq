import math
import argparse
from pathlib import Path
import subprocess
import multiprocessing as mp

import logging

from coqstoq.build.project import Project, Split
from coqstoq.build.build_projects import BuildInstructions, N_JOBS_PER_BUILD

logger = logging.getLogger(__name__)

def has_makefile(project_loc: Path) -> bool:
    children = [p.name for p in project_loc.iterdir()]
    make_names = ["Makefile", "GNUmakefile", "makefile"]
    return any(name in children for name in make_names)


def has_coqproject(project_loc: Path) -> bool:
    return (project_loc / "_CoqProject").exists()


def locate_v_files(project_loc: Path) -> list[str]:
    v_files: list[str] = []
    for p in project_loc.glob("**/*.v"):
        if p.is_file():
            v_files.append(str(p.relative_to(project_loc)))
    return v_files


def arbitrary_project_build(project: Project, coqstoq_loc: Path) -> BuildInstructions:
    project_loc = coqstoq_loc / project.workspace
    if has_makefile(project_loc):
        make_cmd = ["make", "-j", str(N_JOBS_PER_BUILD)]
        return BuildInstructions(project, instrs=[make_cmd])
    elif has_coqproject(project_loc):
        coq_makefile_cmd = ["coq_makefile", "-f", "_CoqProject", "-o", "Makefile.coq"]
        make_cmd = ["make", "-f", "Makefile.coq", "-j", str(N_JOBS_PER_BUILD)]
        return BuildInstructions(project, instrs=[coq_makefile_cmd, make_cmd])
    else:
        coq_makefile_cmd = [
            "coq_makefile",
            *locate_v_files(project_loc),
            "-o",
            "Makefile.coq",
        ]
        make_cmd = ["make", "-f", "Makefile.coq", "-j", str(N_JOBS_PER_BUILD)]
        return BuildInstructions(project, instrs=[coq_makefile_cmd, make_cmd])


SPLITS = [Split.from_name("train-sft"), Split.from_name("train-rl")]


def get_builds(coqstoq_loc: Path) -> list[BuildInstructions]:
    builds: list[BuildInstructions] = []
    for split in SPLITS:
        for project_loc in (coqstoq_loc / split.dir_name).iterdir():
            project = Project(
                dir_name=project_loc.name,
                split=split,
                commit_hash=None,
                compile_args=[],
            )
            builds.append(arbitrary_project_build(project, coqstoq_loc))
    return builds

def run_build(instructions: BuildInstructions):
    logger.info(f"Building {instructions.project.dir_name}")
    for instr in instructions.instrs:
        try:
            result = subprocess.run(
                instr, cwd=instructions.project.workspace.resolve(), capture_output=True, timeout=600
            )
            if result.returncode != 0:
                msg = f"Failed to build {instructions.project.dir_name}. To debug, run: {instr}."
                logger.warning(msg)
                return
        except subprocess.TimeoutExpired:
            msg = f"Timed out while building {instructions.project.dir_name}. Command: {instr}."
            logger.warning(msg)
            return
    logger.info(f"Successfully built {instructions.project.dir_name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Build CoqStoq projects on your machine.")
    default_num_jobs = math.ceil(mp.cpu_count() / N_JOBS_PER_BUILD / 2)
    parser.add_argument("--n_jobs", type=int, default=default_num_jobs)
    args = parser.parse_args()

    COQSTOQ_LOC = Path.cwd()
    LOG_LOC = Path("logs/build-arbitrary.log")
    LOG_LOC.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_LOC,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    print(f"Starting build of arbitrary projects. N jobs: {args.n_jobs}")

    builds = get_builds(COQSTOQ_LOC)

    with mp.Pool(processes=args.n_jobs) as pool:
        pool.map(run_build, builds)
