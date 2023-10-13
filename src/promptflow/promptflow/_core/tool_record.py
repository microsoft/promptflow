# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import collections

from promptflow._internal import RecordStorage, ToolProvider, tool


class ToolRecord(ToolProvider):
    @tool
    def completion(toolType: str, *args, **kwargs) -> str:
        # "AzureOpenAI" =  args[0], this is type indicator, there may be more than one indicators
        prompt_tmpl = args[1]
        prompt_tpl_inputs = args[2]
        working_folder = args[3]

        hashDict = {}
        for keyword in prompt_tpl_inputs:
            if keyword in kwargs:
                hashDict[keyword] = kwargs[keyword]
        hashDict["prompt"] = prompt_tmpl
        hashDict = collections.OrderedDict(sorted(hashDict.items()))

        real_item = RecordStorage.get_record(working_folder, hashDict)
        return real_item


@tool
def just_return(toolType: str, *args, **kwargs) -> str:
    return ToolRecord().completion(toolType, *args, **kwargs)
