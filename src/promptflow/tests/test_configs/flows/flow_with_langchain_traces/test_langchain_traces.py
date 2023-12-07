import os

from langchain.agents.agent_types import AgentType
from langchain.agents.initialize import initialize_agent
from langchain.agents.load_tools import load_tools
from langchain.llms.openai import AzureOpenAI

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection
from promptflow.integrations.langchain import PromptFlowCallbackHandler


@tool
def test_langchain_traces(question: str, conn: AzureOpenAIConnection):
    os.environ["AZURE_OPENAI_API_KEY"] = conn.api_key
    os.environ["OPENAI_API_VERSION"] = conn.api_version
    os.environ["AZURE_OPENAI_ENDPOINT"] = conn.api_base

    llm = AzureOpenAI(
        temperature=0.7,
        deployment_name="text-ada-001",
    )
    tools = load_tools(["llm-math"], llm=llm)
    agent = initialize_agent(
        tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=False,
        callbacks = [PromptFlowCallbackHandler()])
    try:
        return agent.run(question)
    except Exception as e:
        return str(e)
