from __future__ import annotations
from typing import Any, Optional, Literal
import sys, os
import time
import math
import socket
import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from werkzeug.wrappers import Request, Response
import logging
import subprocess
import multiprocessing as mp

from werkzeug.serving import run_simple
from werkzeug.wrappers import Request, Response
from threading import Lock
import requests
# from jsonrpc import JSONRPCResponseManager, dispatcher

from coqstoq.checker_server.problem_server import CheckResult
from coqstoq.interface import ProblemId, ProblemIdError

COQSTOQ_LOC = Path.cwd()
TIMEOUT = 120



class Counter:
    def __init__(self):
        self.__count = 0
        self.__lock = Lock()

    def thump(self):
        with self.__lock:
            self.__count += 1
            return self.__count

    def get(self):
        with self.__lock:
            return self.__count

class CoqServerTimeoutError(Exception):
    pass

@dataclass
class CoqProblemServer:
    port: int
    process: subprocess.Popen[bytes]
    lock: Lock
    last_used: int

    @property
    def url(self) -> str:
        return f"http://localhost:{self.port}/"

    def check_health(self) -> bool:
        if self.process.poll() is not None:
            return False
        return True
    
    def wait_for_start(self, session: requests.Session, timeout: int): 
        total_time = 0
        wait_interval = 0.1
        while True:
            try:
                response = session.get(self.url)
                if response.status_code == 200:
                    break
            except requests.ConnectionError:
                time.sleep(wait_interval)
                total_time += wait_interval 
                if total_time >= timeout:
                    raise CoqServerTimeoutError(
                        f"Coq server at {self.url} did not start within {timeout} seconds."
                    )
    
    def send_request(self, proof: str, timeout: int) -> requests.Response:
        request = {
            "jsonrpc": "2.0",
            "method": "check_proof",
            "params": {
                "proof": proof,
            },
            "id": 1,
        }
        session = requests.Session()
        start = time.time()
        self.wait_for_start(session, timeout)
        end = time.time()
        new_timeout = timeout - (end - start)
        if new_timeout <= 0:
            raise CoqServerTimeoutError(
                f"Coq server at {self.url} did not respond within {timeout} seconds."
            )
        try:
            response = session.post(self.url, json=request, timeout=new_timeout)
            return response
        except requests.Timeout:
            raise CoqServerTimeoutError(
                f"Request to Coq server at {self.url} timed out after {timeout} seconds."
            )
        finally:
            session.close()




MAX_CLIENTS = math.ceil(mp.cpu_count() / 8)
assert MAX_CLIENTS >= 1


clients: dict[ProblemId, list[CoqProblemServer]] = {}
client_dict_lock = Lock()  # need to hold this to modify `clients`
counter = Counter()


@dataclass
class NoSpace:
    pass


@dataclass
class Space:
    pass


@dataclass
class SpaceAfterRemoval:
    problem_id: ProblemId
    client_idx: int
    last_used: int


SpaceResult = Space | NoSpace | SpaceAfterRemoval


def space_available() -> SpaceResult:
    count = 0
    locked_count = 0
    kick_candidate: Optional[SpaceAfterRemoval] = None
    for prob_id, client_list in clients.items():
        for i, client in enumerate(client_list):
            count += 1
            if client.lock.locked():  # safe when holding decision_lock
                locked_count += 1
            else:
                if (
                    kick_candidate is None
                    or client.last_used < kick_candidate.last_used
                ):
                    kick_candidate = SpaceAfterRemoval(
                        problem_id=prob_id,
                        client_idx=i,
                        last_used=client.last_used,
                    )
    if count < MAX_CLIENTS:
        return Space()
    if locked_count < MAX_CLIENTS:
        assert (
            kick_candidate is not None
        ), "There should be a kick candidate if we have more clients than allowed."
        return kick_candidate
    return NoSpace()


PROBLEM_SERVER_LOC = "coqstoq/checker_server/problem_server.py"


def get_args(split: str, idx: int, coqstoq_loc: Path, port: int) -> list[str]:
    return [
        "poetry",
        "run",
        "python3",
        str(coqstoq_loc / PROBLEM_SERVER_LOC),
        split,
        str(idx),
        str(coqstoq_loc),
        str(port),
    ]


def get_open_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def add_client(split: str, idx: int, coqstoq_loc: Path) -> CoqProblemServer:
    key = ProblemId(split, idx)
    if key not in clients:
        clients[key] = []
    port = get_open_port()
    args = get_args(split, idx, coqstoq_loc, port)
    process = subprocess.Popen(args)
    new_server = CoqProblemServer(
        port=port,
        process=process,
        lock=Lock(),
        last_used=counter.thump(),
    )
    new_server.lock.acquire(blocking=True)
    clients[key].append(new_server)
    return new_server

def teardown_server(server: CoqProblemServer) -> None:
    server.process.terminate()
    server.process.wait()


def get_client(split: str, idx: int, coqstoq_loc: Path) -> Optional[CoqProblemServer]:
    with client_dict_lock:
        key = ProblemId(split, idx)
        if key in clients:
            client_list = clients[key]
            for client in client_list:
                if client.lock.acquire(blocking=False):
                    client.last_used = counter.thump()
                    return client
        space_result = space_available()
        match space_result:
            case Space():
                return add_client(split, idx, coqstoq_loc)
            case NoSpace():
                return None
            case SpaceAfterRemoval(problem_id, client_idx, last_used):
                assert problem_id in clients
                clist = clients[problem_id]
                assert client_idx < len(clist)
                server = clist.pop(client_idx)
                with server.lock:
                    teardown_server(server)
                if len(clist) == 0:
                    del clients[problem_id]
                return add_client(split, idx, coqstoq_loc)

def remove_server(server: CoqProblemServer, problem_id: ProblemId) -> None:
    with client_dict_lock:
        for i, client in enumerate(clients[problem_id]):
            if client.last_used == server.last_used and client.port == server.port:
                clients[problem_id].pop(i)
                if len(clients[problem_id]) == 0:
                    del clients[problem_id]



@dataclass(frozen=True, eq=True)
class ReturnValue:
    return_code: Literal[0, -1, -2] # 0 for OK, -1 for timeout, -2 for internal error
    score: float
    messages: list[str]

    def to_json(self) -> Any:
        return {
            "return_code": self.return_code,
            "score": self.score,
            "messages": self.messages,
        }



def check_problem_solution(problem_id: str, solution: str) -> ReturnValue:
    server: Optional[CoqProblemServer] = None  
    try:
        pid = ProblemId.from_id_str(problem_id)
    except ProblemIdError as e:
        return ReturnValue(
            return_code=-2,
            score=-1,
            messages=[f"Invalid problem_id format: {e}"]

        )
    while server is None:
        server = get_client(pid.split, pid.idx, COQSTOQ_LOC)
        if server is None:
            time.sleep(0.1)
        else:
            if not server.check_health(): 
                teardown_server(server)
                remove_server(server, pid)
                server.lock.release()
                logging.warning(
                    f"Server for {pid.split}:{pid.idx} at port {server.port} is not healthy. Restarting."
                )
                server = None
    try:
        response = server.send_request(solution, TIMEOUT)
        if response.status_code != 200:
            return ReturnValue(
                return_code=-2,
                score=0,
                messages=[
                    f"Internal server error: {response.text}"
                ]
            )
        check_result = CheckResult.from_json(response.json()["result"])
        return ReturnValue(
            return_code=0,
            score=check_result.score,
            messages=check_result.messages
        )

    except CoqServerTimeoutError as e:
        return ReturnValue(
            return_code=-1,
            score=0,
            messages=[f"Coq server request timed out: {e}"]
        )
    
    finally:
        server.last_used = counter.thump()
        server.lock.release()



@Request.application
def application(request: Request):
    if request.path != "/check_problem_solution":
        return Response(
            "Invalid endpoint. Use /check_problem_solution.", status=404, mimetype="text/plain"
        )
    if request.method != "POST":
        return Response(
            "Only POST requests are allowed.", status=405, mimetype="text/plain"
        )
    
    try:
        request_data = request.get_json(force=True)
        problem_id = request_data["problem_id"]
        solution = request_data["solution"]
        result = check_problem_solution(problem_id, solution)
        return Response(
            json.dumps(result.to_json(), indent=2),
            status=200,
            mimetype="application/json"
        )
    except:
        return Response(
            "Invalid JSON format or missing parameters.",
            status=400,
            mimetype="text/plain"
        )


if __name__ == "__main__":
    run_simple("0.0.0.0", 8080, application)

"""
curl -X POST http://localhost:8080 \
  -H "Content-Type: application/json" \
  -d '{
        "jsonrpc": "2.0",
        "method": "check_proof",
        "params": {"split": "val", "idx": 0, "coqstoq_loc": ".", "proof": "Proof. Qed.", "timeout": 30},
        "id": 1
      }'
"""

"""
poetry run gunicorn coqstoq.checker_server.server:application --bind 0.0.0.0:8080 --workers 1 --threads 4
"""