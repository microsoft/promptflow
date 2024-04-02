# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Optional
import re

OPEN_AI_PROTOCOL_TEMPLATE = "azure_open_ai://deployment/{}/model/{}"
OPEN_AI_PROTOCOL_REGEX_PATTERN = OPEN_AI_PROTOCOL_TEMPLATE.format(".*", ".*")

def build_open_ai_protocol(s: Optional[str] = None):
    if not s or re.match(OPEN_AI_PROTOCOL_REGEX_PATTERN, s, re.IGNORECASE):
        return s
    else:
        return OPEN_AI_PROTOCOL_TEMPLATE.format(s, s)