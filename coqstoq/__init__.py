from __future__ import annotations
from typing import Optional, Any
from dataclasses import dataclass

from enum import Enum
from coqstoq.eval_thms import EvalTheorem
from coqstoq.predefined_projects import VAL_SPLIT, TEST_SPLIT, CUTOFF_SPLIT
from coqstoq.create_theorem_lists import load_reference_list
from coqstoq.find_eval_thms import get_eval_thms, get_all_eval_thms, get_eval_thms


class Split(Enum):
    VAL = VAL_SPLIT
    TEST = TEST_SPLIT
    CUTOFF = CUTOFF_SPLIT


def num_theorems(split: Split):
    thm_list = load_reference_list(split.value)
    return len(thm_list)


def get_theorem(split: Split, idx: int) -> EvalTheorem:
    thm_list = load_reference_list(split.value)
    thm_ref = thm_list[idx]
    eval_thms = get_eval_thms(thm_ref.thm_path)
    return eval_thms[thm_ref.thm_idx]


def get_theorem_list(split: Split) -> list[EvalTheorem]:
    eval_thm_dict = get_all_eval_thms(split.value)
    thm_list = load_reference_list(split.value)
    eval_thms: list[EvalTheorem] = []
    for thm_ref in thm_list:
        eval_thms.append(eval_thm_dict[thm_ref.thm_path][thm_ref.thm_idx])
    return eval_thms
