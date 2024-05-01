# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Optional
from promptflow.rag.constants._common import OPEN_AI_PROTOCOL_TEMPLATE


def build_open_ai_protocol(deployment: Optional[str] = None, model: Optional[str] = None):
    if not deployment or not model:
        raise ValueError("Please specify deployment_name and model_name in embeddings_model_config.")
    else:
        return OPEN_AI_PROTOCOL_TEMPLATE.format(deployment, model)
