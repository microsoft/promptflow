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

    def build_query(self, user_persona, query: str):
        # make a call to llm with user_persona and query
        # return the response
        return ""

    def __call__(
        self,
        target: callable,
        max_conversation_turns: int = 5,
        user_persona: List[Dict] = [],
        text: str = "",
        num_queries: int = 5,
    ):
        if num_queries != len(user_persona):
            num_queries = len(user_persona)
        # if not text or not user_persona:
        #     raise ValueError("Text and persona cannot be empty")
        prompty_model_config = {"configuration": self.azure_ai_project}
        current_dir = os.path.dirname(__file__)
        prompty_path = os.path.join(current_dir, "_prompty", "task_query_response.prompty")
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
        for query_response_pair in query_response_list:
            query = query_response_pair["q"]
            response = query_response_pair["r"]
            user_persona_item = user_persona[i]
            i += 1
            # build query from user persona and query
            conversation_starter = self.build_query(user_persona_item, query)
            # call target with larger_query
            self.complete_conversation(conversation_starter, max_conversation_turns, target)

    async def complete_conversation(self, conversation_starter, max_conversation_turns, target):
        # call target with conversation_starter
        # get response
        # call llm to process response and come up with follow up query
        # call target with response
        # repeat until max_conversation_turns
        pass
