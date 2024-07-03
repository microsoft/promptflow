#!/bin/bash
set -eux

build_service() {
    local service_dir=$1
    local image_name=$2

    cd "$service_dir"
    rm -rf ./build
    pf flow build --source . --output ./build --format docker
    cd ./build
    docker build -t "$image_name" .
}

# base directory
BASE_DIR=$(pwd)

# build the async mock back-end api service
cd "$BASE_DIR/../mock_api"
docker build -t fastapi-wait-service .

# build the static DAG async service
build_service "$BASE_DIR/../pf_flows/static_async" "pf-static-async-service"

# build the static DAG sync service
build_service "$BASE_DIR/../pf_flows/static_sync" "pf-static-sync-service"

# build the flexflow async service
build_service "$BASE_DIR/../pf_flows/flex_async" "pf-flex-async-service"