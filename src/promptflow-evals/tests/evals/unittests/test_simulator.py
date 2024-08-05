# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# flake8: noqa: F401
# flake8: noqa: F841


import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from promptflow.evals.synthetic import Simulator


class TestSimulator(unittest.TestCase):
    def setUp(self):
        self.azure_ai_project = {
            "subscription_id": "sub_id",
            "resource_group_name": "rg_name",
            "project_name": "project_name",
        }
        self.simulator = Simulator(azure_ai_project=self.azure_ai_project)

    def test_init_with_valid_project_config(self):
        try:
            Simulator(azure_ai_project=self.azure_ai_project)
        except ValueError:
            self.fail("Simulator.__init__() raised ValueError unexpectedly!")

    def test_init_with_invalid_project_config(self):
        invalid_project = {"subscription_id": None, "resource_group_name": "rg_name", "project_name": "project_name"}
        with self.assertRaises(ValueError):
            Simulator(azure_ai_project=invalid_project)

    @patch("simulator.load_flow", return_value=AsyncMock())
    async def test_call_best_case(self, mock_load_flow):
        target = AsyncMock(return_value={"messages": [{"content": "response"}]})
        result = await self.simulator(
            target=target,
            max_conversation_turns=2,
            tasks=["test_task"],
            text="Hello",
            num_queries=1,
            query_response_generating_prompty=None,
            user_simulator_prompty=None,
            api_call_delay_sec=0,
            query_response_generating_prompty_kwargs={},
            user_simulator_prompty_kwargs={},
            conversation_turns=[],
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].messages[0]["content"], "response")

    @patch("simulator.load_flow", side_effect=Exception("Flow load error"))
    async def test_call_worst_case(self, mock_load_flow):
        target = AsyncMock(return_value={"messages": [{"content": "response"}]})
        with self.assertRaises(RuntimeError):
            await self.simulator(
                target=target,
                max_conversation_turns=2,
                tasks=["test_task"],
                text="Hello",
                num_queries=1,
                query_response_generating_prompty=None,
                user_simulator_prompty=None,
                api_call_delay_sec=0,
                query_response_generating_prompty_kwargs={},
                user_simulator_prompty_kwargs={},
                conversation_turns=[],
            )

    def test_build_prompty_model_config(self):
        config = self.simulator._build_prompty_model_config()
        self.assertEqual(config["configuration"], self.azure_ai_project)

    @patch("simulator.load_flow", return_value=AsyncMock())
    async def test_simulate_with_predefined_turns(self, mock_load_flow):
        target = AsyncMock(return_value={"messages": [{"content": "response"}]})
        conversation_turns = [["Hello"]]
        result = await self.simulator._simulate_with_predefined_turns(
            target=target,
            max_conversation_turns=2,
            conversation_turns=conversation_turns,
            user_simulator_prompty=None,
            user_simulator_prompty_kwargs={},
            api_call_delay_sec=0,
            prompty_model_config={},
        )
        self.assertEqual(len(result), 1)

    @patch("simulator.load_flow", return_value=AsyncMock())
    async def test_extend_conversation_with_simulator_best_case(self, mock_load_flow):
        target = AsyncMock(return_value={"messages": [{"content": "response"}]})
        current_simulation = MagicMock()
        current_simulation.get_length.return_value = 0
        await self.simulator._extend_conversation_with_simulator(
            current_simulation=current_simulation,
            max_conversation_turns=2,
            user_simulator_prompty=None,
            user_simulator_prompty_kwargs={},
            api_call_delay_sec=0,
            prompty_model_config={},
            target=target,
        )
        current_simulation.add_to_history.assert_called()

    @patch("simulator.load_flow", side_effect=Exception("Simulation flow error"))
    async def test_extend_conversation_with_simulator_worst_case(self, mock_load_flow):
        target = AsyncMock(return_value={"messages": [{"content": "response"}]})
        current_simulation = MagicMock()
        current_simulation.get_length.return_value = 0
        with self.assertRaises(Exception):
            await self.simulator._extend_conversation_with_simulator(
                current_simulation=current_simulation,
                max_conversation_turns=2,
                user_simulator_prompty=None,
                user_simulator_prompty_kwargs={},
                api_call_delay_sec=0,
                prompty_model_config={},
                target=target,
            )

    def test_parse_prompty_response_best_case(self):
        response = "{'content': 'This is a test response'}"
        parsed_response = self.simulator._parse_prompty_response(response=response)
        self.assertIn("content", parsed_response)

    def test_parse_prompty_response_worst_case(self):
        response = "invalid response"
        with self.assertRaises(ValueError):
            self.simulator._parse_prompty_response(response=response)

    @patch("simulator.load_flow", return_value=AsyncMock())
    async def test_generate_query_responses_best_case(self, mock_load_flow):
        result = await self.simulator._generate_query_responses(
            text="Hello",
            num_queries=1,
            query_response_generating_prompty=None,
            query_response_generating_prompty_kwargs={},
            prompty_model_config={},
        )
        self.assertIsInstance(result, list)

    @patch("simulator.load_flow", side_effect=Exception("Flow error"))
    async def test_generate_query_responses_worst_case(self, mock_load_flow):
        with self.assertRaises(RuntimeError):
            await self.simulator._generate_query_responses(
                text="Hello",
                num_queries=1,
                query_response_generating_prompty=None,
                query_response_generating_prompty_kwargs={},
                prompty_model_config={},
            )

    @patch("simulator.load_flow", return_value=AsyncMock())
    async def test_create_conversations_from_query_responses_best_case(self, mock_load_flow):
        target = AsyncMock(return_value={"messages": [{"content": "response"}]})
        query_responses = [{"q": "question", "r": "response"}]
        result = await self.simulator._create_conversations_from_query_responses(
            query_responses=query_responses,
            max_conversation_turns=2,
            tasks=["test_task"],
            user_simulator_prompty=None,
            user_simulator_prompty_kwargs={},
            target=target,
            api_call_delay_sec=0,
        )
        self.assertEqual(len(result), 1)

    @patch("simulator.load_flow", side_effect=Exception("Creation error"))
    async def test_create_conversations_from_query_responses_worst_case(self, mock_load_flow):
        target = AsyncMock(return_value={"messages": [{"content": "response"}]})
        query_responses = [{"q": "question", "r": "response"}]
        with self.assertRaises(Exception):
            await self.simulator._create_conversations_from_query_responses(
                query_responses=query_responses,
                max_conversation_turns=2,
                tasks=["test_task"],
                user_simulator_prompty=None,
                user_simulator_prompty_kwargs={},
                target=target,
                api_call_delay_sec=0,
            )

    @patch("simulator.load_flow", return_value=AsyncMock())
    async def test_complete_conversation_best_case(self, mock_load_flow):
        target = AsyncMock(return_value={"messages": [{"content": "response"}]})
        progress_bar = MagicMock()
        result = await self.simulator._complete_conversation(
            conversation_starter="Hello",
            max_conversation_turns=2,
            task="test_task",
            user_simulator_prompty=None,
            user_simulator_prompty_kwargs={},
            target=target,
            api_call_delay_sec=0,
            progress_bar=progress_bar,
        )
        self.assertIsInstance(result, list)

    @patch("simulator.load_flow", side_effect=Exception("Completion error"))
    async def test_complete_conversation_worst_case(self, mock_load_flow):
        target = AsyncMock(return_value={"messages": [{"content": "response"}]})
        progress_bar = MagicMock()
        with self.assertRaises(Exception):
            await self.simulator._complete_conversation(
                conversation_starter="Hello",
                max_conversation_turns=2,
                task="test_task",
                user_simulator_prompty=None,
                user_simulator_prompty_kwargs={},
                target=target,
                api_call_delay_sec=0,
                progress_bar=progress_bar,
            )

    @patch("simulator.load_flow", return_value=AsyncMock())
    async def test_build_user_simulation_response_best_case(self, mock_load_flow):
        result = await self.simulator._build_user_simulation_response(
            task="test_task",
            conversation_history=[{"role": "user", "content": "hello"}],
            user_simulator_prompty=None,
            user_simulator_prompty_kwargs={},
        )
        self.assertIsInstance(result, str)

    @patch("simulator.load_flow", side_effect=Exception("Simulation error"))
    async def test_build_user_simulation_response_worst_case(self, mock_load_flow):
        with self.assertRaises(RuntimeError):
            await self.simulator._build_user_simulation_response(
                task="test_task",
                conversation_history=[{"role": "user", "content": "hello"}],
                user_simulator_prompty=None,
                user_simulator_prompty_kwargs={},
            )

    @patch("simulator.load_flow", return_value=AsyncMock())
    async def test_get_target_response_best_case(self, mock_load_flow):
        target = AsyncMock(return_value={"messages": [{"content": "response"}]})
        conversation_history = MagicMock()
        result = await self.simulator._get_target_response(
            target=target,
            api_call_delay_sec=0,
            conversation_history=conversation_history,
        )
        self.assertEqual(result, "response")

    @patch("simulator.load_flow", side_effect=Exception("Target error"))
    async def test_get_target_response_worst_case(self, mock_load_flow):
        target = AsyncMock(return_value={"messages": [{"content": "response"}]})
        conversation_history = MagicMock()
        with self.assertRaises(Exception):
            await self.simulator._get_target_response(
                target=target,
                api_call_delay_sec=0,
                conversation_history=conversation_history,
            )

    async def test_call_with_default_parameters(self):
        # Mock the target callable to be used in the test
        mock_target = AsyncMock(return_value={"result": "mocked_result"})

        # Call the Simulator with default parameters
        result = await self.simulator(target=mock_target, text="Hello, world!")

        # Assert the target callable was called with the expected arguments
        mock_target.assert_called_once_with(
            conversation_history=[],
            tasks=[],
            turn={"user": {"text": "Hello, world!"}},
            num_queries=5,
            query_response_generating_prompty=None,
            user_simulator_prompty=None,
            api_call_delay_sec=1,
            query_response_generating_prompty_kwargs={},
            user_simulator_prompty_kwargs={},
        )

        # Check the result to verify correct processing
        self.assertEqual(result["result"], "mocked_result")

    async def test_call_with_custom_parameters(self):
        # Mock the target callable
        mock_target = AsyncMock(return_value={"result": "custom_result"})

        # Call the Simulator with custom parameters
        result = await self.simulator(
            target=mock_target,
            max_conversation_turns=10,
            tasks=[{"task": "test"}],
            text="Custom text",
            num_queries=3,
            query_response_generating_prompty="Generate a response",
            user_simulator_prompty="Simulate a user",
            api_call_delay_sec=2,
            query_response_generating_prompty_kwargs={"key1": "value1"},
            user_simulator_prompty_kwargs={"key2": "value2"},
        )

        # Assert the target callable was called with the expected arguments
        mock_target.assert_called_once_with(
            conversation_history=[],
            tasks=[{"task": "test"}],
            turn={"user": {"text": "Custom text"}},
            num_queries=3,
            query_response_generating_prompty="Generate a response",
            user_simulator_prompty="Simulate a user",
            api_call_delay_sec=2,
            query_response_generating_prompty_kwargs={"key1": "value1"},
            user_simulator_prompty_kwargs={"key2": "value2"},
        )

        # Check the result to verify correct processing
        self.assertEqual(result["result"], "custom_result")

    async def test_call_with_long_conversation_history(self):
        # Mock the target callable
        mock_target = AsyncMock(return_value={"result": "long_history_result"})

        # Prepare a long conversation history
        conversation_history = [{"user": {"text": f"Message {i}"}} for i in range(15)]

        # Use patch to mock the _get_conversation_history method
        with patch.object(Simulator, "_get_conversation_history", return_value=conversation_history):
            result = await self.simulator(target=mock_target, max_conversation_turns=5, text="New message")

        # Assert the target callable was called
        mock_target.assert_called_once()

        # Verify the conversation history size respects max_conversation_turns
        self.assertTrue(len(mock_target.call_args[1]["conversation_history"]) <= 5)

        # Check the result to verify correct processing
        self.assertEqual(result["result"], "long_history_result")

    async def test_call_with_empty_text(self):
        # Mock the target callable
        mock_target = AsyncMock(return_value={"result": "empty_text_result"})

        # Call the Simulator with an empty text
        result = await self.simulator(target=mock_target, text="")

        # Assert the target callable was called
        mock_target.assert_called_once()

        # Check the result to verify correct processing
        self.assertEqual(result["result"], "empty_text_result")

    async def test_call_with_empty_tasks_list(self):
        # Mock the target callable
        mock_target = AsyncMock(return_value={"result": "empty_tasks_result"})

        # Call the Simulator with an empty tasks list
        result = await self.simulator(
            target=mock_target,
            tasks=[],
            num_queries=10,  # Intentionally high to test against empty task list
            text="Task test",
        )

        # Assert that the target callable was called once
        mock_target.assert_called_once()

        # Check the result to verify correct processing
        self.assertEqual(result["result"], "empty_tasks_result")
