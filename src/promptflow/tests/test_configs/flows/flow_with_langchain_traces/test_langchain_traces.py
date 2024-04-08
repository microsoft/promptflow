import os

from langchain.chat_models import AzureChatOpenAI
from langchain_core.messages import HumanMessage
from langchain.agents.agent_types import AgentType
from langchain.agents.initialize import initialize_agent
from langchain.agents.load_tools import load_tools

from promptflow.core import tool
from promptflow.connections import AzureOpenAIConnection
from promptflow.integrations.langchain import PromptFlowCallbackHandler


@tool
def test_langchain_traces(question: str, conn: AzureOpenAIConnection):
    os.environ["AZURE_OPENAI_API_KEY"] = conn.api_key
    os.environ["OPENAI_API_VERSION"] = conn.api_version
    os.environ["AZURE_OPENAI_ENDPOINT"] = conn.api_base

    model = AzureChatOpenAI(
        temperature=0.7,
        azure_deployment="gpt-35-turbo",
    )

    tools = load_tools(["llm-math"], llm=model)
    # Please keep use agent to enable customized CallBack handler
    agent = initialize_agent(
        tools, model, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=False,
        callbacks=[PromptFlowCallbackHandler()]
    )
    message = HumanMessage(
        content=question
    )

    try:
        return agent.run(message)
    except Exception as e:
        return str(e)
