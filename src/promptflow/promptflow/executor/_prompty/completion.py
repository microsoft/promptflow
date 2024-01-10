# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
from promptflow import tool
from promptflow.connections import AzureOpenAIConnection
from promptflow.tools.aoai import AzureOpenAI

AOAI_ENDPOINT_ENV = "AZURE_OPENAI_ENDPOINT"
AOAI_KEY_ENV = "AZURE_OPENAI_API_KEY"


@tool
def completion(prompt_tpl_file: str, **kwargs):
    with open(prompt_tpl_file, "r") as f:
        prompt_tpl = f.read()
    ignore_index = prompt_tpl.rfind("---")
    aoai_endpoint = os.environ.get(AOAI_ENDPOINT_ENV)
    if not aoai_endpoint:
        raise Exception(f"Please set {AOAI_ENDPOINT_ENV} environment variable to your endpoint.")
    else:
        print(f"Using Azure OpenAI endpoint \"{aoai_endpoint}\".")
    if AOAI_KEY_ENV not in os.environ:
        raise Exception(f"Please set {AOAI_KEY_ENV} environment variable as the credential.")
    prompt_tpl = prompt_tpl[ignore_index+4:]
    conn = AzureOpenAIConnection(api_key=None, api_base=None)
    aoai = AzureOpenAI(conn)
    print(f"Calling LLM with the prompt and following parameters: {kwargs}")
    return aoai.chat(prompt=prompt_tpl, **kwargs)
