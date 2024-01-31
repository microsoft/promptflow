import os

from langchain import hub
from langchain.agents import AgentExecutor, create_react_agent
from langchain.agents.load_tools import load_tools
from langchain_openai.chat_models import AzureChatOpenAI

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection
from promptflow.integrations.langchain import PromptFlowCallbackHandler


@tool
def test_langchain_traces(question: str, conn: AzureOpenAIConnection):
    os.environ["AZURE_OPENAI_API_KEY"] = conn.api_key
    os.environ["OPENAI_API_VERSION"] = conn.api_version
    os.environ["AZURE_OPENAI_ENDPOINT"] = conn.api_base

    llm = AzureChatOpenAI(
        temperature=0.7,
        azure_deployment="gpt-35-turbo",
    )
    tools = load_tools(["llm-math"], llm=llm)
    prompt = hub.pull("hwchase17/react")
    agent = create_react_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, callbacks=[PromptFlowCallbackHandler()])
    return agent_executor.invoke({"input": question})
