from __future__ import annotations
from typing import Optional
import subprocess
import yaml
import os
import json
import argparse
from typing import Any
from pathlib import Path
from dataclasses import dataclass

from coqpyt.lsp.structs import ResponseError
from coqstoq.predefined_projects import PREDEFINED_PROJECTS, HOARETUT
from coqstoq.eval_thms import (
    Project,
    Split,
    find_eval_theorems,
    CoqComplieError,
    CoqCompileTimeoutError,
    EvalTheorem,
)

TEST_THMS_LOC = Path("test-theorems")
REPORTS_LOC = Path("test-theorems-reports")


def save_theorems(project: Project, file: Path, thms: list[EvalTheorem]):
    assert file.is_relative_to(project.workspace)
    file_relpath = file.relative_to(project.workspace)
    save_loc = (
        Path(project.split.thm_dir_name) / project.dir_name / file_relpath
    ).with_suffix(".json")
    if not save_loc.parent.exists():
        save_loc.parent.mkdir(parents=True)
    with open(save_loc, "w") as f:
        json.dump([thm.to_json() for thm in thms], f, indent=2)


def get_eval_thms(file: Path) -> list[EvalTheorem]:
    with open(file) as f:
        thms = json.load(f)
        return [EvalTheorem.from_json(thm) for thm in thms]


def get_all_eval_thms(split: Split, coqstoq_loc: Path) -> dict[Path, list[EvalTheorem]]:
    thm_loc = coqstoq_loc / split.thm_dir_name
    assert thm_loc.exists()
    all_thms: dict[Path, list[EvalTheorem]] = {}
    for thm_file_loc in thm_loc.glob("**/*.json"):
        assert thm_file_loc.is_relative_to(coqstoq_loc)
        rel_thm_file_loc = thm_file_loc.relative_to(coqstoq_loc)
        all_thms[rel_thm_file_loc] = get_eval_thms(thm_file_loc)
    return all_thms


@dataclass
class TheoremReport:
    successful_files: list[Path]
    errored_files: list[Path]
    timed_out_files: list[Path]
    lsp_error_files: list[Path]
    num_theorems: int

    def print_summary(self):
        print(
            f"Num Files: {len(self.successful_files)}; Num Theorems: {self.num_theorems}"
        )
        if 0 < len(self.errored_files):
            print("Compile Errors:" + "".join([f"\n\t{f}" for f in self.errored_files]))
        if 0 < len(self.timed_out_files):
            print(
                "Timeout Errors:" + "".join([f"\n\t{f}" for f in self.timed_out_files])
            )
        if 0 < len(self.lsp_error_files):
            print("LSP Errors:" + "".join([f"\n\t{f}" for f in self.lsp_error_files]))

    @property
    def unsuccessful_files(self):
        return self.errored_files + self.timed_out_files + self.lsp_error_files

    def to_json(self) -> Any:
        return {
            "successful_files": [str(f) for f in self.successful_files],
            "errored_files": [str(f) for f in self.errored_files],
            "timed_out_files": [str(f) for f in self.timed_out_files],
            "lsp_error_files": [str(f) for f in self.lsp_error_files],
            "num_theorems": self.num_theorems,
        }

    @classmethod
    def from_json(cls, data: Any) -> TheoremReport:
        return cls(
            [Path(f) for f in data["successful_files"]],
            [Path(f) for f in data["errored_files"]],
            [Path(f) for f in data["timed_out_files"]],
            [Path(f) for f in data["lsp_error_files"]],
            data["num_theorems"],
        )


def find_project_theormes(project: Project, timeout: int) -> TheoremReport:
    print(project.workspace)
    successful_files: list[Path] = []
    errored_files: list[Path] = []
    timed_out_files: list[Path] = []
    lsp_errored_files: list[Path] = []
    num_thms: int = 0
    for file in project.workspace.glob("**/*.v"):
        print(f"Checking {file}")
        try:
            thms = find_eval_theorems(project, file, timeout)
            print(f"Found {len(thms)} theorems in {file}")
            save_theorems(project, file, thms)
            successful_files.append(file)
            num_thms += len(thms)
        except CoqComplieError as e:
            print(f"Could not compile {file}; Error: {e}")
            errored_files.append(file)
            continue
        except CoqCompileTimeoutError as e:
            print(f"Compilation timed out for {file}; Error; {e}")
            timed_out_files.append(file)
            continue
        except ResponseError as e:
            print(f"Got Coq-LSP response error for {file}.")
            lsp_errored_files.append(file)
            continue
    return TheoremReport(
        successful_files,
        errored_files,
        timed_out_files,
        lsp_errored_files,
        num_thms,
    )


def unique_names(projects: list[Project]) -> bool:
    names = set()
    for p in projects:
        if p.dir_name in names:
            return False
        names.add(p.dir_name)
    return True


def find_project(proj_name: str) -> Project:
    assert unique_names(PREDEFINED_PROJECTS)
    for p in PREDEFINED_PROJECTS:
        if p.dir_name == proj_name:
            return p
    raise ValueError(f"Could not find project with name {proj_name}")


def validate_report(p: Project, theorem_report: TheoremReport):
    """
    Each success should have a file of theorems on disk.
    No failures should have a file of theorems on disk.
    The number of successes plus the number of failures should equal the number of
    ".v" files in the project workspace.
    """
    counted_thms = 0
    for s in theorem_report.successful_files:
        assert s.is_relative_to(p.workspace)
        saved_thms_loc = p.thm_path / s.relative_to(p.workspace).with_suffix(".json")
        assert saved_thms_loc.exists()
        with open(saved_thms_loc) as f:
            thms = json.load(f)
            counted_thms += len(thms)
    assert counted_thms == theorem_report.num_theorems

    for s in theorem_report.unsuccessful_files:
        assert s.is_relative_to(p.workspace)
        saved_thms_loc = p.thm_path / s.relative_to(p.workspace).with_suffix(".json")
        assert not saved_thms_loc.exists()

    total_reported_files = len(theorem_report.successful_files) + len(
        theorem_report.unsuccessful_files
    )
    assert total_reported_files == len(list(p.workspace.glob("**/*.v")))


@dataclass
class EvalReport:
    project: Project
    report: TheoremReport

    def to_json(self) -> Any:
        return {
            "project": self.project.to_json(),
            "report": self.report.to_json(),
        }

    @classmethod
    def from_json(cls, json_data: Any) -> EvalReport:
        return cls(
            Project.from_json(json_data["project"]),
            TheoremReport.from_json(json_data["report"]),
        )

TIMEOUT = 120

def create_predefined_coqstoq_theorems():
    reports: list[EvalReport] = []

    os.makedirs(REPORTS_LOC, exist_ok=True)
    assert unique_names(PREDEFINED_PROJECTS)
    for project in PREDEFINED_PROJECTS:
        report = find_project_theormes(project, TIMEOUT)
        validate_report(project, report)
        eval_report = EvalReport(project, report)
        reports.append(eval_report)
        with open(REPORTS_LOC / f"{project.dir_name}.json", "w") as f:
            json.dump(eval_report.to_json(), f, indent=2)

    print()
    for r in reports:
        print(f"<<<<< Project: {r.project.dir_name} >>>>>")
        r.report.print_summary()



def get_commit_hash(project_dir: Path) -> Optional[str]:
    git_dir_out = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=project_dir,
        capture_output=True,
    )

    if git_dir_out.returncode != 0:
        return None

    git_dir = Path(git_dir_out.stdout.decode().strip())
    if git_dir.parent.resolve() != project_dir.resolve():
        return None

    commit_hash_bytes = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_dir,
        check=True,
        capture_output=True,
    )
    if commit_hash_bytes.returncode != 0:
        return None

    commit_hash = commit_hash_bytes.stdout.decode().strip()
    return commit_hash



def read_yaml_compile_args(project_name: str, yaml_file: Path) -> list[str]:
     with open(yaml_file, "r") as f:
        data = yaml.safe_load(f)
        assert project_name in data, f"Project {project_name} not found in {yaml_file}"
        assert "compile_args" in data[project_name], f"Project {project_name} does not have compile_args in {yaml_file}"
        compile_args = data[project_name]["compile_args"]
        return compile_args


"""
Create coqstoq theorems for a set of custom projects.
"""
def create_custom_coqstoq_theorems(custom_split_name: str):
    custom_split = Split.from_name(custom_split_name)
    custom_repos_loc = Path.cwd() / custom_split.dir_name
    if not custom_repos_loc.exists():
        raise ValueError(
            f"Could not find custom repos directory {custom_repos_loc} for {custom_split_name}."
        ) 
    
    split_config = Path.cwd() / f"{custom_split_name}.yaml"
    if not split_config.exists():
        raise ValueError(
            f"Could not find split config file {split_config} for {custom_split_name}."
        )

    reports: list[EvalReport] = []
    os.makedirs(REPORTS_LOC, exist_ok=True)
    for custom_project in custom_repos_loc.iterdir():
        project_commit = get_commit_hash(custom_project)
        project_compile_args = read_yaml_compile_args(
            custom_project.name, split_config
        )
        print("Project compile args:", project_compile_args)
        project = Project(
            dir_name=custom_project.name,
            split=custom_split,
            commit_hash=project_commit,
            compile_args=project_compile_args,
        ) 
        report = find_project_theormes(project, TIMEOUT)
        validate_report(project, report)
        eval_report = EvalReport(project, report)
        reports.append(eval_report)
        with open(REPORTS_LOC / f"{project.dir_name}.json", "w") as f:
            json.dump(eval_report.to_json(), f, indent=2)

    print()
    for r in reports:
        print(f"<<<<< Project: {r.project.dir_name} >>>>>")
        r.report.print_summary()



if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create coqstoq theorems."
    )
    parser.add_argument(
        "--custom-split-name",
        type=str,
        default=None,
        help="Path to a directory containing custom repos.",
    )

    args = parser.parse_args()

    if args.custom_split_name is not None:
        create_custom_coqstoq_theorems(args.custom_split_name)
    else:
        create_predefined_coqstoq_theorems()