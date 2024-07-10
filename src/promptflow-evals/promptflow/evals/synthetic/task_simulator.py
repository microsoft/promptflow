# flake8: noqa
# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import os
from typing import Any, Dict, List

from promptflow.client import load_flow


class TaskSimulator:
    def __init__(self, azure_ai_project: Dict[str, Any], credential=None):
        """
        Initializes the task simulator with a project scope.

        :param azure_ai_project: Dictionary defining the scope of the project. It must include the following keys:
            - "subscription_id": Azure subscription ID.
            - "resource_group_name": Name of the Azure resource group.
            - "project_name": Name of the Azure Machine Learning workspace.
        :type azure_ai_project: Dict[str, Any]
        :param credential: Azure credentials to authenticate the user. If None, the default credentials are used.
        :type credential: Any
        """
        if not all(key in azure_ai_project for key in ["subscription_id", "resource_group_name", "project_name"]):
            raise ValueError("azure_ai_project must contain keys: subscription_id, resource_group_name, project_name")
        # check the value of the keys in azure_ai_project is not none
        if not all(azure_ai_project[key] for key in ["subscription_id", "resource_group_name", "project_name"]):
            raise ValueError("subscription_id, resource_group_name and project_name must not be None")
        self.azure_ai_project = azure_ai_project
        self.azure_ai_project["api_version"] = "2024-02-15-preview"
        self.credential = credential

    async def build_query(self, *, user_persona, conversation_history, user_simulator_prompty):
        # make a call to llm with user_persona and query
        # return the response
        try:
            if not user_simulator_prompty:
                current_dir = os.path.dirname(__file__)
                prompty_path = os.path.join(current_dir, "_prompty", "task_simulate_with_persona.prompty")
            else:
                raise NotImplementedError("Custom prompty not supported yet")
            _flow = load_flow(source=prompty_path, model={"configuration": self.azure_ai_project})
            response = _flow(user_persona=user_persona, conversation_history=conversation_history)
            ## TODO: Fix the way the response is formatted
            fixed_response = response.replace("'", '"')
        except Exception as e:
            print("Something went wrong running the prompty")
            raise e
        # print(f"Response from user simulator prompty: {fixed_response}")
        # print(f"Type of sim prompty response: {type(fixed_response)}")
        # import pdb; pdb.set_trace()
        try:
            user_simulator_prompty_response = json.loads(fixed_response)
        except Exception as e:
            print("Something went wrong parsing the user_simulator_prompty_response output")
            raise e
        print(f"User simulator prompty response: {user_simulator_prompty_response}")
        return user_simulator_prompty_response

    async def __call__(
        self,
        target: callable,
        max_conversation_turns: int = 5,
        user_persona: List[Dict] = [],
        text: str = "",
        num_queries: int = 5,
        query_response_generating_prompty: str = None,
        user_simulator_prompty: str = None,
    ):
        if num_queries != len(user_persona):
            num_queries = len(user_persona)
        # if not text or not user_persona:
        #     raise ValueError("Text and persona cannot be empty")
        prompty_model_config = {"configuration": self.azure_ai_project}
        if not query_response_generating_prompty:
            current_dir = os.path.dirname(__file__)
            prompty_path = os.path.join(current_dir, "_prompty", "task_query_response.prompty")
        else:
            raise NotImplementedError("Custom prompty not supported yet")
        try:
            _flow = load_flow(source=prompty_path, model=prompty_model_config)
            query_responses = _flow(
                text=text,
                num_queries=num_queries,
            )
        except Exception as e:
            print("Something went wrong running the prompty")
            raise e
        try:
            query_response_list = json.loads(query_responses)
        except Exception as e:
            print("Something went wrong parsing the prompty output")
            raise e
        i = 0
        all_conversations = []
        for query_response_pair in query_response_list:
            query = query_response_pair["q"]
            response = query_response_pair["r"]
            print(f"Query: {query} Expected Response: {response}")
            user_persona_item = user_persona[i]
            i += 1
            conversation = await self.complete_conversation(
                conversation_starter=query,
                max_conversation_turns=max_conversation_turns,
                user_persona=user_persona_item,
                user_simulator_prompty=user_simulator_prompty,
                target=target,
            )
            all_conversations.append(
                {
                    "messsages": conversation,
                    "finish_reason": ["stop"],
                    "context": f"User persona: {user_persona_item} Expected response: {response}",
                    "$schema": "http://azureml/sdk-2-0/ChatConversation.json",
                }
            )
        return all_conversations

    async def complete_conversation(
        self, *, conversation_starter, max_conversation_turns, user_persona, user_simulator_prompty, target
    ):
        conversation_history = [
            {
                "role": "user",
                "content": conversation_starter,
            }
        ]
        while len(conversation_history) < max_conversation_turns:
            response = await target(
                messages={"messages": conversation_history}, stream=False, session_state=None, context=None
            )
            messages_list = response["messages"]
            latest_message = messages_list[-1]
            response_from_target = latest_message["content"]
            conversation_history.append(
                {
                    "role": "assistant",
                    "content": response_from_target,
                }
            )
            if len(conversation_history) == max_conversation_turns:
                break
            response_from_user_simulating_prompty = await self.build_query(
                user_persona=user_persona,
                conversation_history=conversation_history,
                user_simulator_prompty=user_simulator_prompty,
            )
            conversation_history.append(response_from_user_simulating_prompty)
        return conversation_history
