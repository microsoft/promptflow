from pathlib import Path

import pytest

from promptflow._sdk.entities._chat_group._chat_agent import ChatAgent
from promptflow._sdk.entities._chat_group._chat_group import ChatGroup

PROMOTFLOW_ROOT = Path(__file__) / "../../../.."

TEST_ROOT = Path(__file__).parent.parent.parent
FLOWS_DIR = TEST_ROOT / "test_configs/flows"


@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestChatGroup:
    def test_basic_invoke(self):
        joke_master = ChatAgent(flow=FLOWS_DIR / "chat_group_joke_master")
        criticizer = ChatAgent(flow=FLOWS_DIR / "chat_group_criticizer")

        chat_group = ChatGroup(
            agents=[joke_master, criticizer],
            # entry_agent=joke_master,
            max_turns=10,
            max_tokens=1000,
            max_time=1000,
            inputs={
                "request": {
                    "type": str,
                    "default": "Tell me a joke",
                },
                "comments": {
                    "type": str,
                    "default": "I like it",
                },
            },
            outputs={
                "result": {
                    "type": str,
                    "reference": criticizer.outputs.result,
                }
            },
        )
        assert chat_group
        # joke_master.set_inputs(text=criticizer.outputs.output ? chat_group.inputs.request)
        # criticizer.set_inputs(words=joke_master.outputs.output, chat_history=chat_group.chat_history)
