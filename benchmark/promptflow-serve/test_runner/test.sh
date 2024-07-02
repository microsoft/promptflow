#!/bin/bash

# print usage if no test arg
if [ -z "${1:-}" ]; then
    echo "Usage: $0 <test>"
    echo "Available tests: mock, staticasync, staticsync, flexasync"
    exit 1
fi

# Source the .env file to export the variables
if [ -f settings.env ]; then
  cat settings.env
  set -o allexport
  source settings.env
  set +o allexport
else
  echo "settings.env file not found!"
  exit 1
fi

# List of required environment variables
required_vars=(
    USERS
    HATCH_RATE
    RUN_TIME
    PROMPTFLOW_WORKER_NUM
    PROMPTFLOW_WORKER_THREADS
)

# Check if all required environment variables are set and not empty
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "Error: Environment variable $var is not set or is empty."
        exit 1
    fi
done

case $1 in
    mock)
        export LOCUST_FILE=mock_locustfile.py
        export TARGET_HOST=http://localhost:50001/
        export TARGET_TYPE=mock
        ENV_PREP="docker-compose up fastapi-wait-service -d"
        ;;
    staticasync)
        export LOCUST_FILE=pf_locustfile.py
        export TARGET_HOST=http://localhost:8081/
        export TARGET_TYPE=pf_static_async
        ENV_PREP="docker-compose up fastapi-wait-service pf-static-async-service -d"
        ;;
    staticsync)
        export LOCUST_FILE=pf_locustfile.py
        export TARGET_HOST=http://localhost:8082/
        export TARGET_TYPE=pf_static_sync
        ENV_PREP="docker-compose up fastapi-wait-service pf-static-sync-service -d"
        ;;
    flexasync)
        export LOCUST_FILE=pf_locustfile.py
        export TARGET_HOST=http://localhost:8083/
        export TARGET_TYPE=pf_flex_async
        ENV_PREP="docker-compose up fastapi-wait-service pf-flex-async-service -d"
        ;;
    *)
        echo "Invalid endpoint. Available endpoints: mock, staticasync, staticsync, flexasync"
        exit 1
        ;;
esac

# prepare the env, starting at least the mock service
echo "Stopping existing services..."
docker-compose down --remove-orphans || echo "docker-compose down encountered an error, but we're ignoring it."

echo "Starting the services..."
$ENV_PREP

echo "Waiting before running tests..."
secs=$((30))
while [ $secs -gt 0 ]; do
   echo -ne "$secs\033[0K\r"
   sleep 1
   : $((secs--))
done

echo "Running Locust tests against $1 endpoint..."
./run_locust.sh
