# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import collections
import hashlib

from promptflow._internal import ToolProvider, tool


class ToolRecord(ToolProvider):
    def __init__(self):
        pass

    @tool
    def completion(toolType: str, *args, **kwargs) -> str:
        # From aoai.py, check
        keywords = args[1]
        hashDict = {}
        for keyword in keywords:
            if keyword in kwargs:
                hashDict[keyword] = kwargs[keyword]
        hashDict["prompt"] = args[0]
        hashDict = collections.OrderedDict(sorted(hashDict.items()))
        hashValue = hashlib.sha1(str(hashDict).encode("utf-8")).hexdigest()
        return hashValue


@tool
def just_return(toolType: str, *args, **kwargs) -> str:
    return ToolRecord().completion(toolType, *args, **kwargs)
