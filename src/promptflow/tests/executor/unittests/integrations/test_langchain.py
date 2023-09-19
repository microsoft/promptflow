import pytest

from langchain.schema import AgentAction, AgentFinish

from promptflow.integrations.langchain import LangChainEventType, PromptFlowCallbackHandler


@pytest.mark.unittest
class TestLangchain:
    def test_langchain_traces(self):
        handler = PromptFlowCallbackHandler()
        handler.on_llm_start(serialized={"test": "test"}, prompts=["test"])
        handler.on_chain_start(serialized={"test": "test"}, inputs={"test": "test"})
        handler.on_tool_start(serialized={"test": "test"}, input_str="test")
        handler.on_agent_action(action=AgentAction("test", "test", "test"))
        assert handler._events_stack == [
            LangChainEventType.LLM,
            LangChainEventType.CHAIN,
            LangChainEventType.TOOL,
            LangChainEventType.AGENT
        ]
        handler.on_agent_finish(finish=AgentFinish({"test": "test"}, "test"))
        handler.on_tool_end(output="test")
        handler.on_chain_end(outputs={"test": "test"})
        handler.on_llm_end(response=None)
        assert len(handler._events_stack) == 0

    def test_langchain_traces_with_unpaired_events(self):
        handler = PromptFlowCallbackHandler()
        handler.on_llm_start(serialized={"test": "test"}, prompts=["test"])
        # Missing on_chain_start
        # Missing on_tool_start
        handler.on_tool_end(output="test")
        handler.on_chain_end(outputs={"test": "test"})
        handler.on_llm_end(response=None)
        assert len(handler._events_stack) == 0

        handler = PromptFlowCallbackHandler()
        handler.on_llm_start(serialized={"test": "test"}, prompts=["test"])
        handler.on_chain_start(serialized={"test": "test"}, inputs={"test": "test"})
        handler.on_tool_start(serialized={"test": "test"}, input_str="test")
        # Missing on_tool_end
        # Missing on_chain_end
        handler.on_llm_end(response=None)
        assert len(handler._events_stack) == 0
