#!/bin/bash

# List of required environment variables
required_vars=(
    HOST_PROJECT_PATH
    LOCUST_FILE
    TARGET_HOST
    USERS
    HATCH_RATE
    RUN_TIME
    TARGET_TYPE
)

# Check if all required environment variables are set and not empty
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "Error: Environment variable $var is not set or is empty."
        exit 1
    fi
done

docker run --rm -it \
    --network=host \
    -v $HOST_PROJECT_PATH/benchmark/promptflow-serve/test_runner:/mnt/locust \
    locustio/locust \
    -f /mnt/locust/$LOCUST_FILE \
    --host=$TARGET_HOST \
    --headless \
    -u $USERS \
    -r $HATCH_RATE \
    --run-time $RUN_TIME \
    --html=/mnt/locust/locust-results/${TARGET_TYPE}_report_u${USERS}_h${HATCH_RATE}.html \
    --csv=/mnt/locust/locust-results/${TARGET_TYPE}_report_u${USERS}_h${HATCH_RATE} \
    --print-stats
