#!/bin/bash

# set/update PROMPTFLOW_WORKER_NUM based on CPU core num
update_process_num() {
    process_num=$(grep -c processor /proc/cpuinfo)
    if [[ -z "${PROMPTFLOW_WORKER_NUM}" ]]; then
        echo "PROMPTFLOW_WORKER_NUM not set, setting PROMPTFLOW_WORKER_NUM to cpu core numner: $process_num"
        export PROMPTFLOW_WORKER_NUM=$process_num
    else
        # make sure PROMPTFLOW_WORKER_NUM is no larger than (2 * the number of cores)
        max_process=$((process_num * 2))
        if [[ $PROMPTFLOW_WORKER_NUM -gt $max_process ]]; then
            echo "PROMPTFLOW_WORKER_NUM is too large, setting PROMPTFLOW_WORKER_NUM to (2 * the number of cores)=$max_process"
            export PROMPTFLOW_WORKER_NUM=$max_process
        fi
    fi
}

# check whether a model is a promptflow model
is_pf_model() {
    [[ -f "${1}/MLmodel" || -f "${1}/flow.dag.yaml" ]]
}

# auto-detect PROMPTFLOW_RUN_MODE for pf serving scenario.
auto_detect_env() {
    if [[ -z "${PROMPTFLOW_RUN_MODE}" ]]; then
        echo "detecting promptflow run mode..."
        if [[ -z "${AZUREML_MODEL_DIR}" && -z "${PROMPTFLOW_PROJECT_PATH}" ]]; then
            export PROMPTFLOW_RUN_MODE="compute"
        else
            # if PROMPTFLOW_PROJECT_PATH is set, this is a serving environment
            if [[ -z "${AZUREML_MODEL_DIR}" ]]; then
                export PROMPTFLOW_RUN_MODE="serving"
            else
                # check model file to determine if it is MIR serving deployment or runtime deployment
                # will remove this once we didn't support MIR runtime for both 1P & 3P
                if is_pf_model ${AZUREML_MODEL_DIR}; then
                    export PROMPTFLOW_RUN_MODE="serving"
                else
                    sub_dirs=(${AZUREML_MODEL_DIR}/*)
                    # only has one sub dir, it is a model deployment
                    if [[ ${#sub_dirs[@]} == 1 ]]; then
                        model_dir=${sub_dirs[0]}
                        is_pf_model ${model_dir} && export PROMPTFLOW_RUN_MODE="serving"
                    fi
                fi
            fi
        fi
        echo "PROMPTFLOW_RUN_MODE: ${PROMPTFLOW_RUN_MODE}"
    fi
    # only update the settings for pf serving scenario
    if [[ ${PROMPTFLOW_RUN_MODE} == "serving" ]]; then
        update_process_num
    fi
    export PROMPTFLOW_AUTO_DETECT="true"
}

auto_detect_env
