# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

# This file captures promptflow-evals dependencies on private API of promptflow.
# In case changes are made please reach out to promptflow-evals team to update the dependencies.

def _get_pf_evals_dependencies():
    from promptflow.azure.operations._async_run_uploader import AsyncRunUploader

    return AsyncRunUploader
