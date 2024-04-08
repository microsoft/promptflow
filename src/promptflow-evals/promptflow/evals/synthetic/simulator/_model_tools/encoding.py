# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging
from enum import Enum
from typing import Any, Dict, Optional

import json5 as json

logger = logging.getLogger(__name__)

DEFAULT_INDENT = 2


class Encoding(Enum):
    JSON = "json"
    XML = "xml"


def encode_example(
    example: Dict[str, Any], encoding: Encoding = Encoding.JSON, indent: Optional[int] = DEFAULT_INDENT
) -> str:
    """
    Encode examples into an encoding format.

    :param example: example to encode
    :type example: Dict[str, Any]
    :param encoding: encoding format to use
    :type encoding: Encoding
    :param indent: number of spaces to indent JSON output
    :type indent: Optional[int]
    :return: encoded example
    :rtype: str
    """
    if encoding.value == Encoding.JSON.value:
        # Dump JSON with keys double-quoted and final comma removed
        return json.dumps(example, indent=indent, quote_keys=True, trailing_commas=False)
    if encoding.value == Encoding.XML.value:
        raise NotImplementedError("XML encoding not implemented.")
    raise ValueError(f"Unknown encoding {encoding} ({type(encoding)}).")
