"""Integration tests for MiniMax with prompt flow.

These tests verify end-to-end functionality by calling the MiniMax API.
They require a valid MINIMAX_API_KEY environment variable.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add the example directory to path
EXAMPLE_DIR = Path(__file__).absolute().parents[2] / "examples" / "flex-flows" / "chat-with-minimax"
sys.path.insert(0, str(EXAMPLE_DIR))

# Skip all integration tests if no API key
pytestmark = pytest.mark.skipif(
    not os.environ.get("MINIMAX_API_KEY"),
    reason="MINIMAX_API_KEY not set"
)


class TestMiniMaxAPIChat:
    """Test MiniMax API chat completions via OpenAI SDK."""

    def test_basic_chat_completion(self):
        """Test a simple chat completion via MiniMax API."""
        from openai import OpenAI

        client = OpenAI(
            api_key=os.environ["MINIMAX_API_KEY"],
            base_url="https://api.minimax.io/v1",
        )
        response = client.chat.completions.create(
            model="MiniMax-M2.5",
            messages=[{"role": "user", "content": "Say hello in one word."}],
            max_tokens=10,
            temperature=0.7,
        )
        assert response.choices[0].message.content
        assert len(response.choices[0].message.content) > 0

    def test_chat_with_system_message(self):
        """Test chat with a system prompt."""
        from openai import OpenAI

        client = OpenAI(
            api_key=os.environ["MINIMAX_API_KEY"],
            base_url="https://api.minimax.io/v1",
        )
        response = client.chat.completions.create(
            model="MiniMax-M2.5",
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Reply in one sentence."},
                {"role": "user", "content": "What is prompt flow?"},
            ],
            max_tokens=100,
            temperature=0.5,
        )
        assert response.choices[0].message.content
        assert len(response.choices[0].message.content) > 5

    def test_chat_streaming(self):
        """Test streaming chat completion."""
        from openai import OpenAI

        client = OpenAI(
            api_key=os.environ["MINIMAX_API_KEY"],
            base_url="https://api.minimax.io/v1",
        )
        stream = client.chat.completions.create(
            model="MiniMax-M2.5",
            messages=[{"role": "user", "content": "Count from 1 to 3."}],
            max_tokens=30,
            temperature=0.5,
            stream=True,
        )
        chunks = []
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                chunks.append(chunk.choices[0].delta.content)
        full_response = "".join(chunks)
        assert len(full_response) > 0


class TestMiniMaxOpenAIConnection:
    """Test MiniMax via promptflow's OpenAIConnection."""

    def test_openai_connection_with_minimax(self):
        """Test creating an OpenAI client from connection config with MiniMax base URL."""
        from promptflow.connections import OpenAIConnection
        from promptflow.tools.common import init_openai_client

        conn = OpenAIConnection(
            api_key=os.environ["MINIMAX_API_KEY"],
            base_url="https://api.minimax.io/v1",
        )
        client = init_openai_client(conn)
        response = client.chat.completions.create(
            model="MiniMax-M2.5",
            messages=[{"role": "user", "content": "Say hi."}],
            max_tokens=10,
            temperature=0.7,
        )
        assert response.choices[0].message.content

    def test_openai_tool_chat_with_minimax(self):
        """Test the promptflow OpenAI tool's chat function with MiniMax."""
        from promptflow.connections import OpenAIConnection
        from promptflow.tools.openai import chat

        conn = OpenAIConnection(
            api_key=os.environ["MINIMAX_API_KEY"],
            base_url="https://api.minimax.io/v1",
        )
        prompt = "system:\nYou are helpful.\n\nuser:\nSay hello."
        result = chat(
            connection=conn,
            prompt=prompt,
            model="MiniMax-M2.5",
            max_tokens=20,
            temperature=0.5,
        )
        assert result
        assert len(str(result)) > 0


class TestMiniMaxFlowExample:
    """Test the MiniMax chat flow example end-to-end."""

    def test_flow_direct_call(self):
        """Test calling the flow directly."""
        from flow import ChatFlow, get_minimax_config

        config = get_minimax_config(model="MiniMax-M2.5")
        flow = ChatFlow(config, max_total_token=4096)
        result = flow("What is 2 + 2? Reply with just the number.")
        assert result
        assert "4" in result
