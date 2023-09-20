import pytest

from langchain.schema import AgentAction, AgentFinish

from promptflow.integrations.langchain import LangChainEventType, PromptFlowCallbackHandler


@pytest.mark.unittest
class TestLangchain:
    def get_handler(self):
        class MockTracer():
            def __init__(self):
                self._trace_stack = []

            def _push(self, trace):
                self._trace_stack.append(trace)

            def _pop(self, output=None, error=None):
                self._trace_stack.pop()

        handler = PromptFlowCallbackHandler()
        handler._tracer = MockTracer()
        return handler

    def test_langchain_traces(self):
        handler = self.get_handler()
        handler.on_agent_action(action=AgentAction("test", "test", "test"))
        handler.on_tool_start(serialized={"test": "test"}, input_str="test")
        handler.on_chain_start(serialized={"test": "test"}, inputs={"test": "test"})
        handler.on_llm_start(serialized={"test": "test"}, prompts=["test"])
        assert handler._events_stack == [
            LangChainEventType.AGENT,
            LangChainEventType.TOOL,
            LangChainEventType.CHAIN,
            LangChainEventType.LLM
        ]
        assert len(handler._tracer._trace_stack) == 4
        handler.on_llm_end(response=None)
        handler.on_chain_end(outputs={"test": "test"})
        handler.on_tool_end(output="test")
        handler.on_agent_finish(finish=AgentFinish({"test": "test"}, "test"))
        assert len(handler._events_stack) == 0
        assert len(handler._tracer._trace_stack) == 0

    def test_langchain_traces_with_unpaired_events(self):
        handler = self.get_handler()
        handler.on_tool_start(serialized={"test": "test"}, input_str="test")
        # Missing on_chain_start
        # Missing on_llm_start
        assert len(handler._tracer._trace_stack) == 1
        handler.on_llm_end(response=None)
        handler.on_chain_end(outputs={"test": "test"})
        assert len(handler._tracer._trace_stack) == 1
        handler.on_tool_end(output="test")
        assert len(handler._events_stack) == 0
        assert len(handler._tracer._trace_stack) == 0

        handler = self.get_handler()
        handler.on_tool_start(serialized={"test": "test"}, input_str="test")
        handler.on_chain_start(serialized={"test": "test"}, inputs={"test": "test"})
        handler.on_llm_start(serialized={"test": "test"}, prompts=["test"])
        assert len(handler._tracer._trace_stack) == 3
        # Missing on_chain_end
        # Missing on_llm_end
        handler.on_tool_end(output="test")
        assert len(handler._events_stack) == 0
        assert len(handler._tracer._trace_stack) == 0
