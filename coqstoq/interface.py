from __future__ import annotations
from typing import Any, Optional, Generator
from pathlib import Path
from dataclasses import dataclass 
import json
import argparse

from coqstoq.index_thms.eval_thms import EvalTheorem as EvalTheorem
from coqstoq.scripts import get_theorem, get_theorem_list
from coqstoq.check import get_theorem_text, get_ground_truth, get_prefix

COQSTOQ_LOC = Path.cwd()

class ProblemIdError(Exception):
    """Custom exception for errors related to ProblemId parsing."""
    pass

@dataclass(frozen=True, eq=True)
class ProblemId:
    split: str
    idx: int

    def to_str(self) -> str:
        return f"{self.split}:{self.idx}"

    @classmethod
    def from_id_str(cls, problem_id: str) -> ProblemId:
        parts = problem_id.split(":")
        if len(parts) != 2:
            raise ProblemIdError(f"Invalid problem_id format: {problem_id}. Expected format 'split:idx'.")
        split = parts[0]
        try:
            idx = int(parts[1])
        except ValueError:
            raise ProblemIdError(f"Invalid index in problem_id: {problem_id}. Index must be an integer.")
        return cls(split=split, idx=idx)


@dataclass(frozen=True, eq=True)
class ToolArgs:
    tool_name: str
    kwargs: dict[str, Any]


@dataclass(frozen=True, eq=True)
class ExtraInfo:
    language: str
    example_name: str
    prompt: str
    ground_truth: Optional[str] 
    need_tools_kwargs: bool
    tools_kwargs: list[ToolArgs] 

    def to_json(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "example_name": self.example_name,
            "prompt": self.prompt,
            "ground_truth": self.ground_truth,
            "need_tools_kwargs": self.need_tools_kwargs,
            "tools_kwargs": {
                tool.tool_name: tool.kwargs for tool in self.tools_kwargs
            }  
        }


@dataclass(frozen=True, eq=True)
class RewardModel:
    style: str
    ground_truth: Optional[str]

    def to_json(self) -> dict[str, Any]:
        return {
            "style": self.style,
            "ground_truth": self.ground_truth,
        }


@dataclass(frozen=True, eq=True)
class Example:
    data_source: str
    prompt: str
    ability: str
    reward_model: RewardModel
    extra_info: ExtraInfo

    def to_json(self) -> dict[str, Any]:
        return {
            "data_source": self.data_source,
            "prompt": self.prompt,
            "ability": self.ability,
            "reward_model": self.reward_model.to_json(),
            "extra_info": self.extra_info.to_json(),
        }


def get_user_prompt(theorem: EvalTheorem) -> str:
    theorem_text = get_theorem_text(theorem, COQSTOQ_LOC)
    context = get_prefix(theorem, COQSTOQ_LOC)

    return (
        f"The theorem I'm trying to prove is\n"
        f"```\n{theorem_text}\n```\n"
        f"#####\n\n"
        "The file context in which I'm writing the proof is \n"
        f"```\n{context}\n```\n"
        f"#####\n\n"
        "Start the proof with the follwing tactic:\n"
        f"```\nProof\n```\n"
    )

LANGUAGE = "coq"


def create_verl_example(split: str, idx: int, theorem: EvalTheorem, coqstoq_loc: Path) -> Example:
    user_prompt = get_user_prompt(theorem)
    ground_truth = get_ground_truth(theorem, coqstoq_loc)
    example_id = ProblemId(split=split, idx=idx).to_str()

    extra_info = ExtraInfo(
        language=LANGUAGE,
        example_name=example_id,
        prompt=user_prompt,
        ground_truth=ground_truth,
        need_tools_kwargs=True,
        tools_kwargs=[
            ToolArgs(
                tool_name="tools/execute_coq",
                kwargs={
                    "example_name": example_id,
                }
            )
        ],
    )

    reward_model = RewardModel(
        style="execution",
        ground_truth=ground_truth,
    )

    return Example(
        data_source="coqstoq",
        prompt=user_prompt,
        ability="programming",
        reward_model=reward_model,
        extra_info=extra_info,
    )

def create_verl_examples(split: str, coqstoq_loc: Path) -> Generator[Example, None, None]: 
    theorems = get_theorem_list(split, coqstoq_loc)
    examples: list[Example] = []
    for idx, theorem in enumerate(theorems):
        yield create_verl_example(split, idx, theorem, coqstoq_loc)

def write_verl_examples(split: str, coqstoq_loc: Path, output_file: Path) -> None:
    assert not output_file.exists(), f"Output file {output_file} already exists. Please remove it before running this script."
    with output_file.open("a") as fout:
        for ve in create_verl_examples(split, coqstoq_loc):
            ve_data = ve.to_json()
            fout.write(json.dumps(ve_data) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate VERL examples from CoqStoq theorems.")
    parser.add_argument("split", type=str, help="The split of theorems to use (e.g., 'train-sft', 'train-rl', 'val', 'test', 'cutoff').")

    args = parser.parse_args()
    split = args.split

    VERL_LOC = Path("verl")
    if not VERL_LOC.exists():
        VERL_LOC.mkdir()
    
    
    output_loc = VERL_LOC / f"{split}.jsonl"
    write_verl_examples(split, COQSTOQ_LOC, output_loc)



