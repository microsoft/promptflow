# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import re
from typing import Optional
from promptflow.rag.constants._common import OPEN_AI_PROTOCOL_REGEX_PATTERN, OPEN_AI_PROTOCOL_TEMPLATE


def build_open_ai_protocol(s: Optional[str] = None):
    if not s or re.match(OPEN_AI_PROTOCOL_REGEX_PATTERN, s, re.IGNORECASE):
        return s
    else:
        return OPEN_AI_PROTOCOL_TEMPLATE.format(s, s)
