# Introduction

This directory contains scripts to test the throughput scalability of various [PromptFlow](https://microsoft.github.io/promptflow/) flows, using sync/async HTTP calls. It contains:
- A mock API service ([FastAPI](https://fastapi.tiangolo.com/) + [uvicorn](https://www.uvicorn.org/)) and Docker file to run as a service;
- Three different PromptFlow flows which include a node to query the mock API service:
  - A [FlexFlow](https://microsoft.github.io/promptflow/tutorials/flex-flow-quickstart.html)-based flow with an async call to the mock API service;
  - Two [static DAG](https://microsoft.github.io/promptflow/tutorials/quickstart.html) flows, each which call the mock API service, one using an async call, the other sync;
- A set of bash and [Docker Compose](https://docs.docker.com/compose/) scripts to build and run each of the above services;
- A script to run [Locust](https://locust.io/) jobs to measure the scalability of each of the PF flow services.

# Contents

```
├── README.md               (this README file)
├── makefile                (Makefile with the commands to build and run tests)
├── mock_api                (a mock API service which simply waits before returning JSON)
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── pf_flows                (various PromptFlow flows which call the mock API service using sync/async HTTP calls)
│   ├── flex_async          (async flexflow example)
│   │   ├── flow.flex.yaml
│   │   ├── flow.py
│   │   └── requirements.txt
│   ├── static_async        (async static DAG example)
│   │   ├── chat.py
│   │   ├── flow.dag.yaml
│   │   └── requirements.txt
│   └── static_sync         (sync static DAG example)
│       ├── chat.py
│       ├── flow.dag.yaml
│       └── requirements.txt
├── requirements.txt        (pip requirements for developing the tests)
└── test_runner        (scripts to perform scalability tests against each of the PF flows)
    ├── locust_results      (this is where the locust results will be stored)
    ├── build.sh            (builds the docker images for each of the services above)
    ├── docker-compose.yml  (manages starting up all the docker-based services)
    ├── mock_locustfile.py  (locust test spec for testing the capacity of the mock API service)
    ├── pf_locustfile.py    (locust test spec for testing the capacity of the PF flow services)
    ├── run_locust.sh       (locust runner used in the tests)
    ├── settings.env        (env file with the configuration used in the tests)
    └── test.sh             (orchestrates running the tests)
```

# Preparing the environment

## Prerequisites

### Software

Build the provided devcontainer and use it for running tests.

### Hardware

A host machine with at least 8 vCPU threads.

## Building the services

- `make install-requirements`
- `make build`

This script will visit each of the service directories (`mock_api`, `pf_flows/flex_async`, `pf_flows/static_async`, and `pf_flows/static_sync`) and create docker images for each.

Once this is complete, you can verify the services were built with `docker image ls`, for example:
```
REPOSITORY                 TAG       IMAGE ID       CREATED          SIZE
fastapi-wait-service       latest    6bc9152b6b9b   32 minutes ago    184MB
pf-flex-async-service      latest    d14cc15f45ad   33 minutes ago   1.58GB
pf-static-sync-service     latest    8b5ac2dac32c   34 minutes ago   1.58GB
pf-static-async-service    latest    ff2968d3ef11   34 minutes ago   1.58GB
```

To test each of the services, you can try:
- Mock API service: `curl "http://localhost:50001/"`
- Static DAG async PF service: `curl --request POST 'http://localhost:8081/score' --header 'Content-Type: application/json' --data '{"question": "Test question", "chat_history":  []}'`
- Static DAG sync PF service: `curl --request POST 'http://localhost:8082/score' --header 'Content-Type: application/json' --data '{"question": "Test question", "chat_history":  []}'`
- FlexFlow async PF service: `curl --request POST 'http://localhost:8083/score' --header 'Content-Type: application/json' --data '{"question": "Test question", "chat_history":  []}'`

## Running each of the throughput tests

The mock API service simply waits every time a request is made, and returns JSON after the wait has ended. The wait time is configurable, but set to 1 second in the docker compose script.

In order to test the throughput latency of PF flows which call this service, we first need to establish a baseline of throughput for this mock service. Once we have this, we would expect all PF flows to have the same or similar throughput latency as all they are programmed to do is call this service and return.

The `benchmark/promptflow-serve/makefile` supports four tests:
- `make test-mock`: Run the throughput tests on the mock API service to determine a baseline.
- `make test-staticsync`: Run the throughput tests on the PF static sync DAG flow service.
- `make test-staticasync`: Run the throughput tests on the PF static async DAG flow service.
- `make test-flexasync`: Run the throughput tests on the PF flex flow async service.

## Test parameters

They can be controlled in the `benchmark/promptflow-serve/test_runner/settings.env` file.

## Results

The results are stored in the `/locust-results` folder. There are interactive HTML reports which present the results as graphs as well.
