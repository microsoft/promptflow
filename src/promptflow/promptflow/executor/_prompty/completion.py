# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection
from promptflow.tools.aoai import AzureOpenAI


@tool
def completion(prompt_tpl_file: str, **kwargs):
    with open(prompt_tpl_file, "r") as f:
        prompt_tpl = f.read()
    ignore_index = prompt_tpl.rfind("---")
    prompt_tpl = prompt_tpl[ignore_index+4:]
    conn = AzureOpenAIConnection(api_key=None, api_base=None)
    aoai = AzureOpenAI(conn)
    return aoai.chat(prompt=prompt_tpl, **kwargs)
