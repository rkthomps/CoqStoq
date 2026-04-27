import argparse
from pathlib import Path
from coqstoq.eval_thms import Split
from coqstoq.create_theorem_lists import load_reference_list
from coqstoq.find_eval_thms import get_eval_thms
from coqstoq.eval_thms import EvalTheorem, get_file_hash


def get_theorem_text(thm: EvalTheorem, coqstoq_loc: Path) -> str:
    orig_file_loc = coqstoq_loc / thm.project.workspace / thm.path
    assert orig_file_loc.exists()
    assert (
        get_file_hash(orig_file_loc) == thm.hash
    ), f"Hash mismatch for file {orig_file_loc}"
    orig_contents = orig_file_loc.read_text()
    orig_lines = orig_contents.splitlines()
    thm_lines = orig_lines[
        thm.theorem_start_pos.line : thm.theorem_end_pos.line + 1
    ].copy()
    thm_lines[-1] = thm_lines[-1][: thm.theorem_end_pos.column]
    thm_lines[0] = thm_lines[0][thm.theorem_start_pos.column :]
    return "\n".join(thm_lines)


def main(split_str: str, search_str: str, thm_path: Path, coqstoq_loc: Path):
    assert split_str in ["val", "test", "cutoff"]
    split = Split.from_name(split_str)
    reference_list = load_reference_list(split, coqstoq_loc)
    for i, thm_ref in enumerate(reference_list):
        if thm_ref.thm_path != Path("test-theorems" / thm_path).with_suffix(".json"):
            continue
        path_thms = get_eval_thms(coqstoq_loc / thm_ref.thm_path)
        thm = path_thms[thm_ref.thm_idx]
        thm_text = get_theorem_text(thm, coqstoq_loc)
        if search_str in thm_text:
            print(f"Found match to search in {thm_ref.thm_path} at with theorem id {i}")
            print("Theorem text:")
            print(thm_text)
            print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Search for a string within theorem text in a CoqStoq split."
    )
    parser.add_argument(
        "split",
        choices=["val", "test", "cutoff"],
        help="Which split to search in.",
    )
    parser.add_argument(
        "search_str",
        help="String to search for in theorem text.",
    )
    parser.add_argument(
        "thm_path",
        type=Path,
        help="Path under test-theorems/ (without .json suffix), e.g. compcert/common/Memdata.v",
    )
    parser.add_argument(
        "--coqstoq-loc",
        type=Path,
        default=Path.cwd(),
        help="Path to the CoqStoq repo (default: current working directory).",
    )

    args = parser.parse_args()
    main(args.split, args.search_str, args.thm_path, args.coqstoq_loc)
