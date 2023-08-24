import os

import openai
from langchain.agents.agent_types import AgentType
from langchain.agents.initialize import initialize_agent
from langchain.agents.load_tools import load_tools
from langchain.llms.openai import AzureOpenAI

from promptflow import tool
from promptflow._core.langchain_handler import get_langchain_callback_manager
from promptflow.connections import AzureOpenAIConnection


@tool
def my_python_tool(question: str, conn: AzureOpenAIConnection):
    os.environ["OPENAI_API_KEY"] = conn.api_key
    openai.api_base = conn.api_base
    openai.api_type = conn.api_type
    openai.api_version = conn.api_version

    llm = AzureOpenAI(
        temperature=0.7,
        deployment_name="text-davinci-003",
    )
    manager = get_langchain_callback_manager()
    tools = load_tools(["llm-math"], llm=llm)
    agent = initialize_agent(
        tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=False,
        callback_manager=manager)
    return agent.run(question)