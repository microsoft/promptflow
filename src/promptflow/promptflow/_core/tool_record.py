# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import collections

from promptflow._internal import MyStorageRecord, ToolProvider, tool


class ToolRecord(ToolProvider):
    @tool
    def completion(toolType: str, *args, **kwargs) -> str:
        # From aoai.py, check
        keywords = args[2]
        hashDict = {}
        for keyword in keywords:
            if keyword in kwargs:
                hashDict[keyword] = kwargs[keyword]
        hashDict["prompt"] = args[1]
        hashDict = collections.OrderedDict(sorted(hashDict.items()))

        real_item = MyStorageRecord.getRecord(hashDict)
        return real_item


@tool
def just_return(toolType: str, *args, **kwargs) -> str:
    return ToolRecord().completion(toolType, *args, **kwargs)
