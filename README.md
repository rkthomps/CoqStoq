# CoqStoq
Benchmark and Dataset for Training and Testing Coq proof search tools.  

### Using the benchmark  
- This dataset is intended to be used via docker.  
- To see how to use this dataset outside of docker, simply reference the [Dockerfile](Dockerfile)

## Cloning the repository
```
git clone -b deepproof-full https://github.com/rkthomps/CoqStoq --recurse-submodules
```

## Building the docker image
Please allow for 1-2 hours to build the image.
```
cd CoqStoq
docker build -t coqstoq-full .
```

## Verification Server
1. Starting the verification server
```
# Note the number of workers **MUST BE 1**. The number of threads should be approximately # cpus / 4
docker run -p 8080:8080 coqstoq-full poetry run gunicorn coqstoq.checker_server.server:application --bind 0.0.0.0:8080 --workers 1 --threads 8
```

2. Calling the verification server
```
Once the verification engine is started, you can call it (from the host machine) through requests like the following:
curl -X POST http://localhost:8080/check_problem_solution   -H "Content-Type: application/json"   -d '{
    "problem_id": "val:0",
    "solution": "Proof. Qed."
}'
```

3. **You should follow [example.py](example.py) for an example of calling the verification server programatically**. It shows how to call the server in parallel on the first 50 ground truth solutions from the train-sft split.  


## APIs
### Get the available splits:
```
docker run coqstoq-full poetry run python3 api.py get_splits

Expected output:
{
  "splits": [
    "train-sft",
    "train-rl",
    "val",
    "cutoff",
    "test",
  ]
}
```

### Get the number of examples in a split:
```
docker run coqstoq-full poetry run python3 api.py get_num_theorems train-rl

Expected output:
{
  "num_theorems": 80274 
}
```

### Get the relevant information about an example:
```
docker run coqstoq-full poetry run python3 api.py get_theorem_info train-sft 3001 

Expected output:
{
  "split": "train-rl",
  "index": 3001,
  "prefix": ...  # the portion of the file comming before the theorem
  "suffix": ...  # the portion of the file comming after the proof 
  "theorem": ... # the theorem statement
  "groud_truth": ... # the human-written proof
}
```


### Get the relevant information about a range of examples:
```
docker run coqstoq-full poetry run python3 api.py get_theorem_range train-sft 3 5 

Expected output:
[
  {
    "split": "train-rl",
    "index": 3,
    "prefix": ...,
    "suffix": ...,
    "theorem": ...,
    "ground_truth": ...,
  },
  {
    "split": "train-rl",
    "index": 4,
    "prefix": ...,
    "suffix": ...,
    "theorem": ...,
    "ground_truth": ...,
  },
]

```
