from unittest.mock import AsyncMock

import pytest

from promptflow.evals.synthetic._conversation import (
    CallbackConversationBot,
    ConversationRole,
    OpenAIChatCompletionsModel,
)


class MockOpenAIChatCompletionsModel(OpenAIChatCompletionsModel):
    def __init__(self):
        super().__init__(name="mockAIcompletionsModel", endpoint_url="some-url", token_manager="token_manager")

    async def get_conversation_completion(self, messages, session, role):
        return {"response": {}, "request": {}, "time_taken": 0, "full_response": {}}


@pytest.mark.unittest
class TestCallbackConversationBot:
    @pytest.mark.asyncio
    async def test_generate_response_with_valid_callback(self):
        # Mock the callback to return a predefined response
        async def mock_callback(msg):
            return {
                "messages": [{"content": "Test response", "role": "assistant"}],
                "finish_reason": ["stop"],
                "id": "test_id",
                "template_parameters": {},
            }

        # Create an instance of CallbackConversationBot with the mock callback
        bot = CallbackConversationBot(
            callback=mock_callback,
            model=MockOpenAIChatCompletionsModel(),
            user_template="",
            user_template_parameters={},
            role=ConversationRole.ASSISTANT,
            conversation_template="",
            instantiation_parameters={},
        )

        # Mock conversation history and other parameters
        conversation_history = []
        session = AsyncMock()  # Mock any external session or client if needed

        # Call generate_response and verify the result
        response, _, time_taken, result = await bot.generate_response(session, conversation_history, max_history=10)

        assert response["samples"][0] == "Test response"
        assert "stop" in response["finish_reason"]
        assert time_taken >= 0
        assert result["id"] == "test_id"

    @pytest.mark.asyncio
    async def test_generate_response_with_no_callback_response(self):
        # Mock the callback to return an empty result
        async def mock_callback(msg):
            return {}

        # Create an instance of CallbackConversationBot with the mock callback
        bot = CallbackConversationBot(
            callback=mock_callback,
            model=MockOpenAIChatCompletionsModel(),
            user_template="",
            user_template_parameters={},
            role=ConversationRole.ASSISTANT,
            conversation_template="",
            instantiation_parameters={},
        )

        # Mock conversation history and other parameters
        conversation_history = []
        session = AsyncMock()  # Mock any external session or client if needed

        # Call generate_response and verify the result
        response, _, time_taken, result = await bot.generate_response(session, conversation_history, max_history=10)

        assert response["samples"][0] == "Callback did not return a response."
        assert "stop" in response["finish_reason"]
        assert time_taken >= 0
        assert result["id"] is None

    @pytest.mark.asyncio
    async def test_generate_response_with_callback_exception(self):
        # Mock the callback to raise an exception
        async def mock_callback(msg):
            raise RuntimeError("Unexpected error")

        # Create an instance of CallbackConversationBot with the mock callback
        bot = CallbackConversationBot(
            callback=mock_callback,
            model=MockOpenAIChatCompletionsModel(),
            user_template="",
            user_template_parameters={},
            role=ConversationRole.ASSISTANT,
            conversation_template="",
            instantiation_parameters={},
        )

        # Mock conversation history and other parameters
        conversation_history = []
        session = AsyncMock()  # Mock any external session or client if needed

        # Call generate_response and verify the result
        with pytest.raises(RuntimeError) as exc_info:
            await bot.generate_response(session, conversation_history, max_history=10)

        assert "Unexpected error" in str(exc_info.value)
