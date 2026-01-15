"""
Creates a (shuffled) list of theorems referencing theorems created by 
`find_eval_theorems`.
"""

from __future__ import annotations
from typing import Any

import json
import argparse
import random
from pathlib import Path

from dataclasses import dataclass
from coqstoq.eval_thms import Split, EvalTheorem

from coqstoq.predefined_projects import (
    PREDEFINED_PROJECTS,
    TEST_SPLIT,
    VAL_SPLIT,
    CUTOFF_SPLIT,
)


@dataclass(unsafe_hash=True)
class TheoremReference:
    thm_path: Path
    thm_idx: int

    def to_json(self):
        return {"thm_path": str(self.thm_path), "thm_idx": self.thm_idx}

    def to_eval_thm(self) -> EvalTheorem:
        with (Path.cwd() / self.thm_path).open("r") as fin:
            thms = json.load(fin)
            return EvalTheorem.from_json(thms[self.thm_idx])

    @classmethod
    def from_json(cls, data: Any) -> TheoremReference:
        return cls(Path(data["thm_path"]), data["thm_idx"])


def load_reference_list(split: Split, coqstoq_loc: Path) -> list[TheoremReference]:
    theorem_list_loc = coqstoq_loc / split.theorem_list_loc
    with theorem_list_loc.open("r") as fin:
        return [TheoremReference.from_json(thm) for thm in json.load(fin)]


def create_split_list(split: Split, seed: int) -> list[TheoremReference]:
    split_theorems_loc = Path.cwd() / split.thm_dir_name
    assert split_theorems_loc.exists()
    theorem_list: list[TheoremReference] = []
    for thm_file_loc in split_theorems_loc.glob("**/*.json"):
        assert thm_file_loc.is_relative_to(Path.cwd())
        rel_thm_file_loc = thm_file_loc.relative_to(Path.cwd())
        with thm_file_loc.open("r") as fin:
            thms = json.load(fin)
            for idx, _ in enumerate(thms):
                theorem_list.append(TheoremReference(rel_thm_file_loc, idx))
    random.seed(seed)
    random.shuffle(theorem_list)
    return theorem_list


def create_theorem_list(seed: int, split_name: str):
    split = Split.from_name(split_name)
    thm_list = create_split_list(split, seed)
    with open(split.theorem_list_loc, "w") as fout:
        json.dump([thm.to_json() for thm in thm_list], fout, indent=2)


if __name__ == "__main__":
    SEED = 0
    parser = argparse.ArgumentParser(
        description="Create a list of theorems for the given split."
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=SEED,
        help="Seed for shuffling the theorem list.",
    )
    parser.add_argument(
        "split_name",
        type=str,
        help="Name of the split to create a theorem list for.",
    )
        
    args = parser.parse_args()
    create_theorem_list(SEED, args.split_name)
