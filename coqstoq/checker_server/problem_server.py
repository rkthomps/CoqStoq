
"""
Single-threaded server for handindling verification of a  
single problem at a time.
"""

from __future__ import annotations
from typing import Any, Optional, Literal
import sys, os
import time
import socket
import argparse
from dataclasses import dataclass
from pathlib import Path
from werkzeug.wrappers import Request, Response
import logging

from werkzeug.serving import run_simple
import requests
from jsonrpc import JSONRPCResponseManager, dispatcher

from coqpyt.lsp.structs import DiagnosticSeverity

from coqstoq.scripts import get_theorem
from coqstoq.check import get_ground_truth, get_lsp_check_contents, strip_qed
from coqstoq.index_thms.eval_thms import EvalTheorem
from coqstoq.checker_server.lsp_client import ClientWrapper, FastLspClient

logger = logging.getLogger(__name__)

theorem: EvalTheorem | None = None  # The theorem to be checked
coqstoq_loc: Path | None = None  # The path to the CoqStoq repository
client: ClientWrapper | None = None # The wrapper around the coq-lsp client which does the proof checking


"""Given the entire contents of a file to check, use coq-lsp to check for errors."""
def do_check(contents: str) -> list[str]: 
    assert client is not None, "Client must be set before running the server."
    client.write_and_get_steps(contents)
    errors: list[str] = []
    for diagnostic in client.client.lsp_endpoint.diagnostics[client.file_uri]:
        if diagnostic.severity == DiagnosticSeverity.Error:
            errors.append(diagnostic.message)
    return errors


def sanity_check_ground_truth() -> None:
    assert theorem is not None, "Theorem must be set before running the server."
    assert coqstoq_loc is not None, "CoqStoq location must be set before running the server."
    assert client is not None, "Client must be set before running the server."
    ground_truth = strip_qed(get_ground_truth(theorem, coqstoq_loc))
    logger.info(f"***Ground truth****\n{ground_truth}")
    check_contents = get_lsp_check_contents(theorem, ground_truth, coqstoq_loc)
    logger.debug(f"***Contents:***\n {"\n".join(check_contents.splitlines()[-20:])}")
    error_msgs = do_check(check_contents)
    assert len(error_msgs) == 0, (
        f"Ground truth proof for theorem {theorem.path} has {len(error_msgs)} errors.\n"
        f"First 3 errors: {error_msgs[:3]}\n"
    )

@dataclass
class CheckResult:
    score: Literal[0, 1] # 0 for incorrect, 1 for correct
    messages: list[str] # Error messages

    def to_json(self) -> Any:
        return {
            "score": self.score,
            "messages": self.messages,
        }
    
    @classmethod
    def from_json(cls, json_obj: Any) -> CheckResult:
        score = json_obj["score"]
        return cls(
            score=score,
            messages=json_obj["messages"],
        )


@dispatcher.add_method
def check_proof(proof: str) -> CheckResult:
    assert theorem is not None, "Theorem must be set before running the server."
    assert coqstoq_loc is not None, "CoqStoq location must be set before running the server."
    assert client is not None, "Client must be set before running the server."
    check_contents = strip_qed(get_lsp_check_contents(theorem, proof, coqstoq_loc))
    err_msgs = do_check(check_contents)
    if len(err_msgs) == 0:
        return CheckResult(score=1, messages=[]).to_json()
    else:
        return CheckResult(score=0, messages=err_msgs).to_json()


@Request.application
def application(request: requests.models.Response):
    response = JSONRPCResponseManager.handle(request.data, dispatcher)
    return Response(response.json, mimetype="application/json")



if __name__ == "__main__":
    # from waitress import serve
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "split",
        help=(
            "Split for which the server is running.\n"
            "Examples include 'train', 'val', 'test', 'cutoff'"
        ),
    )
    parser.add_argument("idx", type=int, help=("Index of the theorem in the split.\n"))
    parser.add_argument(
        "coqstoq_loc", type=str, help=("Path to the CoqStoq repository.")
    )
    parser.add_argument("port", type=int, help=("Port to run the server on."))

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    split = args.split
    idx = args.idx
    port = args.port
    coqstoq_loc = Path(args.coqstoq_loc)
    assert coqstoq_loc.exists(), f"Path {coqstoq_loc} does not exist."
    if not coqstoq_loc.name == "CoqStoq":
        logger.warning(
            f"Expected the CoqStoq repository to be in a folder named 'CoqStoq', "
            f"Make sure you are pointing to the correct path."
        )
    
    assert split is not None, "Split must be provided."
    assert idx is not None, "Index must be provided."

    args = parser.parse_args()
    theorem = get_theorem(split, idx, coqstoq_loc)

    fast_client = FastLspClient(
        root_uri=str(theorem.project.workspace.resolve()),
        timeout=120,
    )

    file_loc = theorem.project.workspace / theorem.path
    logger.info("Creating lsp client for file: %s", file_loc)
    try:
        client = ClientWrapper(
            client=fast_client,
            file_uri=str(theorem.project.workspace.resolve() / theorem.path)
        )
        logger.info("Running sanity check on ground truth proof for theorem: %s", theorem.path)
        sanity_check_ground_truth()
        run_simple("localhost", port, application)
    finally:
        logger.info("Shutting down the client.")
        if client is not None:
            client.client.shutdown()
            client.client.exit()

