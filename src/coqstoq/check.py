from __future__ import annotations
from typing import Optional, Any
from pathlib import Path

import os
import logging
from enum import Enum
from dataclasses import dataclass

from coqstoq.eval_thms import EvalTheorem, get_file_hash, compile_file, CoqComplieError


@dataclass
class Result:
    thm: EvalTheorem
    proof: Optional[str]  # Proof found
    time: Optional[float]  # Time in seconds

    def to_json(self) -> Any:
        return {
            "thm": self.thm.to_json(),
            "proof": self.proof,
            "time": self.time,
        }

    @classmethod
    def from_json(cls, json_data: Any) -> Result:
        return cls(
            EvalTheorem.from_json(json_data["thm"]),
            json_data["proof"],
            json_data["time"],
        )


@dataclass
class EvalResults:
    hardware: str  # Description of hardware used
    results: list[Result]

    def to_json(self) -> Any:
        return {
            "hardware": self.hardware,
            "results": [r.to_json() for r in self.results],
        }

    @classmethod
    def from_json(cls, json_data: Any) -> EvalResults:
        return cls(
            json_data["hardware"],
            [Result.from_json(r) for r in json_data["results"]],
        )


def get_check_contents(thm: EvalTheorem, proof_attempt: str, coqstoq_loc: Path) -> str:
    orig_file_loc = coqstoq_loc / thm.project.workspace / thm.path
    assert orig_file_loc.exists()
    assert (
        get_file_hash(orig_file_loc) == thm.hash
    ), f"Hash mismatch for file {orig_file_loc}"
    orig_contents = orig_file_loc.read_text()
    orig_lines = orig_contents.split("\n")
    prefix_lines = orig_lines[: (thm.theorem_end_pos.line + 1)].copy()
    prefix_lines[-1] = prefix_lines[-1][: thm.theorem_end_pos.column]
    suffix_lines = orig_lines[thm.proof_end_pos.line :]
    suffix_lines[0] = suffix_lines[0][thm.proof_end_pos.column :]
    return "\n".join(prefix_lines + [proof_attempt, "Qed."] + suffix_lines)


def get_ground_truth(thm: EvalTheorem, coqstoq_loc: Path) -> str:
    orig_file_loc = coqstoq_loc / thm.project.workspace / thm.path
    assert orig_file_loc.exists()
    assert (
        get_file_hash(orig_file_loc) == thm.hash
    ), f"Hash mismatch for file {orig_file_loc}"
    orig_contents = orig_file_loc.read_text()
    orig_lines = orig_contents.split("\n")
    proof_lines = orig_lines[
        thm.proof_start_pos.line : thm.proof_end_pos.line + 1
    ].copy()
    proof_lines[-1] = proof_lines[-1][: thm.proof_end_pos.column]
    proof_lines[0] = proof_lines[0][thm.proof_start_pos.column :]
    return "\n".join(proof_lines)


def check_result(r: Result, coqstoq_loc: Path) -> bool:
    attempted_proof = r.proof
    if attempted_proof is None:
        return False

    stripped_proof = attempted_proof.strip()
    if stripped_proof.endswith("Qed."):
        use_proof = stripped_proof[: -len("Qed.")]
    else:
        use_proof = stripped_proof

    orig_file_loc = r.thm.project.workspace / r.thm.path
    assert orig_file_loc.exists()
    assert (
        get_file_hash(orig_file_loc) == r.thm.hash
    ), f"Hash mismatch for file {r.thm.project.workspace / r.thm.path}"

    temp_loc = r.thm.project.workspace / "coqstoq_check_temp.v"
    assert not temp_loc.exists()
    compile_file(r.thm.project, orig_file_loc, None)  # Should compile
    try:
        with temp_loc.open("w") as fout:
            fout.write(get_check_contents(r.thm, use_proof, coqstoq_loc))
        compile_file(r.thm.project, temp_loc, None)  # Checking attempt
        return True
    except CoqComplieError:
        return False
    finally:
        os.remove(temp_loc)
