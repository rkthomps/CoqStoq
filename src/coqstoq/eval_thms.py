from __future__ import annotations
import os
import shutil
import argparse
import hashlib
from typing import Optional, Any
from pathlib import Path
from enum import Enum
from dataclasses import dataclass
import subprocess

from coqpyt.coq.structs import TermType, Step, Position as LspPos
from coqpyt.coq.base_file import CoqFile


@dataclass
class Split:
    dir_name: str
    thm_dir_name: str

    @property
    def theorem_list_loc(self) -> Path:
        return Path(f"{self.thm_dir_name}.json")

    def to_json(self) -> Any:
        return {"dir_name": self.dir_name, "thm_dir_name": self.thm_dir_name}

    @classmethod
    def from_json(cls, data: Any) -> Split:
        return cls(data["dir_name"], data["thm_dir_name"])
    
    @classmethod
    def from_name(cls, name: str) -> Split:
        return cls(f"{name}-repos", f"{name}-theorems")


@dataclass
class Project:
    dir_name: str
    split: Split
    commit_hash: Optional[str]
    compile_args: list[str]

    @property
    def workspace(self) -> Path:
        return Path(self.split.dir_name) / self.dir_name

    @property
    def thm_path(self) -> Path:
        return Path(self.split.thm_dir_name) / self.dir_name

    def to_json(self) -> Any:
        return {
            "dir_name": self.dir_name,
            "split": self.split.to_json(),
            "commit_hash": self.commit_hash,
            "compile_args": self.compile_args,
        }

    @classmethod
    def from_json(cls, json_data: Any) -> Project:
        return cls(
            json_data["dir_name"],
            Split.from_json(json_data["split"]),
            json_data["commit_hash"],
            json_data["compile_args"],
        )


@dataclass
class Position:
    line: int
    column: int

    def to_json(self) -> Any:
        return {"line": self.line, "column": self.column}

    @classmethod
    def from_lsp_pos(cls, pos: LspPos) -> Position:
        return cls(pos.line, pos.character)

    @classmethod
    def from_json(cls, data: Any) -> Position:
        return cls(data["line"], data["column"])


@dataclass
class EvalTheorem:
    project: Project
    path: Path  # relative path in the project
    theorem_start_pos: Position  # inclusive
    theorem_end_pos: Position  # inclusive line, exclusive column
    proof_start_pos: Position  # inclusive
    proof_end_pos: Position  # inclusive line, exclusive column
    hash: str  # Hash of file when theorem was collected

    def to_json(self) -> Any:
        return {
            "project": self.project.to_json(),
            "path": str(self.path),
            "theorem_start_pos": self.theorem_start_pos.to_json(),
            "theorem_end_pos": self.theorem_end_pos.to_json(),
            "proof_start_pos": self.proof_start_pos.to_json(),
            "proof_end_pos": self.proof_end_pos.to_json(),
            "hash": self.hash,
        }

    @classmethod
    def from_json(cls, data: Any) -> EvalTheorem:
        return cls(
            Project.from_json(data["project"]),
            Path(data["path"]),
            Position.from_json(data["theorem_start_pos"]),
            Position.from_json(data["theorem_end_pos"]),
            Position.from_json(data["proof_start_pos"]),
            Position.from_json(data["proof_end_pos"]),
            data["hash"],
        )


def is_eval_theorem(termtype: TermType) -> bool:
    match termtype:
        case (
            TermType.THEOREM
            | TermType.LEMMA
            | TermType.FACT
            | TermType.REMARK
            | TermType.COROLLARY
            | TermType.PROPOSITION
            | TermType.PROPERTY
        ):
            return True
        case _:
            return False


def is_end_proof(coq_file: CoqFile, step: Step) -> bool:
    return coq_file.context.expr(step)[0] in [
        "VernacEndProof",
        "VernacExactProof",
        "VernacAbort",
    ]


def extract_proof(coq_file: CoqFile) -> list[Step]:
    term = coq_file.curr_step
    assert is_eval_theorem(coq_file.context.term_type(coq_file.curr_step))
    assert not is_end_proof(coq_file, coq_file.curr_step)
    proof_steps: list[Step] = []
    while not is_end_proof(coq_file, coq_file.curr_step):
        coq_file.exec()
        if coq_file.steps_taken >= len(coq_file.steps):
            raise ValueError(f"Proof at line {term.ast.range.start.line} never ended.")
        proof_steps.append(coq_file.curr_step)
    return proof_steps


def ends_with_qed(proof: list[Step]) -> bool:
    assert 0 < len(proof)
    return proof[-1].text.strip().endswith("Qed.")


def get_file_hash(path: Path) -> str:
    hasher = hashlib.sha256()
    hasher.update(path.read_bytes())
    return hasher.hexdigest()


def get_test_thm(
    project: Project, path: Path, theorem_step: Step, proof_steps: list[Step]
) -> EvalTheorem:
    assert 0 < len(proof_steps)
    assert path.resolve().is_relative_to(project.workspace.resolve())
    rel_path = path.relative_to(project.workspace)
    return EvalTheorem(
        project,
        rel_path,
        Position.from_lsp_pos(theorem_step.ast.range.start),
        Position.from_lsp_pos(theorem_step.ast.range.end),
        Position.from_lsp_pos(proof_steps[0].ast.range.start),
        Position.from_lsp_pos(proof_steps[-1].ast.range.end),
        get_file_hash(path),
    )


class CoqComplieError(Exception):
    pass


class CoqCompileTimeoutError(Exception):
    pass


def compile_file(project: Project, path: Path, timeout: Optional[int]):
    project_loc = project.workspace
    assert project_loc.exists()
    cur_dir = Path.cwd().resolve()
    full_path = path.resolve()
    os.chdir(project_loc)
    tmp_dir = Path("tmp-coqstoq-out")
    assert not tmp_dir.exists()
    os.mkdir(tmp_dir)
    tmp_out_loc = tmp_dir / path.with_suffix(".vo").name
    try:
        # print(["coqc", "-o", tmp_out_loc, *project.compile_args, full_path])
        out = subprocess.run(
            ["coqc", "-o", tmp_out_loc, *project.compile_args, full_path],
            capture_output=True,
            timeout=timeout,
        )
        if out.returncode == 0:
            return None
        else:
            raise CoqComplieError(out.stderr)
    except subprocess.TimeoutExpired:
        raise CoqCompileTimeoutError(f"Compilation timed out for {path}.")
    finally:
        if tmp_out_loc.exists():
            os.remove(tmp_out_loc)
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        os.chdir(cur_dir)


def find_eval_theorems(
    project: Project, path: Path, timeout: Optional[int]
) -> list[EvalTheorem]:
    compile_file(project, path, timeout)
    str_file_path = str(path.resolve())
    str_workspace_path = str(project.workspace.resolve())
    proofs: list[EvalTheorem] = []
    cf_timeout = timeout if timeout is not None else 60
    with CoqFile(
        str_file_path,
        workspace=str_workspace_path,
        timeout=cf_timeout,
        memory_limit=20 * (2**20),
    ) as coq_file:
        while coq_file.steps_taken < len(coq_file.steps):
            tt = coq_file.context.term_type(coq_file.curr_step)
            theorem_step = coq_file.curr_step
            if is_eval_theorem(tt):
                steps = extract_proof(coq_file)
                assert 0 < len(steps)
                if ends_with_qed(steps):
                    test_thm = get_test_thm(project, path, theorem_step, steps)
                    proofs.append(test_thm)
            else:
                coq_file.exec()
    return proofs
