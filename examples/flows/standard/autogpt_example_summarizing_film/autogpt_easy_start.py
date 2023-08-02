from typing import Union

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection


@tool
def autogpt_easy_start(connection: Union[AzureOpenAIConnection, OpenAIConnection], system_prompt: str, user_prompt: str,
                       triggering_prompt: str, functions: list, model_or_deployment_name: str):
    from wiki_search import search
    from python_repl import python
    from autogpt_class import AutoGPT

    full_message_history = []
    tools = [
        search,
        python
    ]
    agent = AutoGPT(
        full_message_history=full_message_history,
        tools=tools,
        system_prompt=system_prompt,
        connection=connection,
        model_or_deployment_name=model_or_deployment_name,
        functions=functions,
        user_prompt=user_prompt,
        triggering_prompt=triggering_prompt
    )
    result = agent.run()
    return result
