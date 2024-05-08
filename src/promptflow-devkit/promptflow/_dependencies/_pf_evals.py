# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

# This file captures promptflow-evals dependencies on private API of promptflow.
# In case changes are made please reach out to promptflow-evals team to update the dependencies.


def _get_pf_evals_dependencies():
    from promptflow._sdk._constants import LINE_NUMBER
    from promptflow._sdk._constants import Local2Cloud

    return {
        "LINE_NUMBER": LINE_NUMBER,
        "Local2Cloud": Local2Cloud
    }
