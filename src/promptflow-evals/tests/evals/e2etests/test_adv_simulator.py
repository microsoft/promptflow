import asyncio
import os
from typing import Any, Dict, List

import pytest


@pytest.mark.usefixtures("recording_injection")
@pytest.mark.e2etest
class TestAdvSimulator:
    def test_adv_sim_init_with_prod_url(self, azure_cred, project_scope):
        os.environ.pop("RAI_SVC_URL", None)
        from promptflow.evals.synthetic import AdversarialSimulator

        azure_ai_project = {
            "subscription_id": project_scope["subscription_id"],
            "resource_group_name": project_scope["resource_group_name"],
            "project_name": project_scope["project_name"],
            "credential": azure_cred,
        }
        simulator = AdversarialSimulator(azure_ai_project=azure_ai_project)
        assert callable(simulator)

    def test_incorrect_scenario_raises_error(self, azure_cred, project_scope):
        os.environ.pop("RAI_SVC_URL", None)
        from promptflow.evals.synthetic import AdversarialSimulator

        azure_ai_project = {
            "subscription_id": project_scope["subscription_id"],
            "resource_group_name": project_scope["resource_group_name"],
            "project_name": project_scope["project_name"],
            "credential": azure_cred,
        }

        async def callback(x):
            return x

        simulator = AdversarialSimulator(azure_ai_project=azure_ai_project)
        with pytest.raises(ValueError):
            asyncio.run(
                simulator(
                    max_conversation_turns=1,
                    max_simulation_results=1,
                    target=callback,
                    scenario="adv_conversation_wrong",
                )
            )

    def test_adv_qa_sim_responds_with_one_response(self, azure_cred, project_scope):
        os.environ.pop("RAI_SVC_URL", None)
        from promptflow.evals.synthetic import AdversarialScenario, AdversarialSimulator

        azure_ai_project = {
            "subscription_id": project_scope["subscription_id"],
            "resource_group_name": project_scope["resource_group_name"],
            "project_name": project_scope["project_name"],
            "credential": azure_cred,
        }

        async def callback(
            messages: List[Dict], stream: bool = False, session_state: Any = None, context: Dict[str, Any] = None
        ) -> dict:
            question = messages["messages"][0]["content"]
            response_from_acs, temperature = question, 0.0
            formatted_response = {
                "content": response_from_acs["result"],
                "role": "assistant",
                "context": {
                    "temperature": temperature,
                },
            }
            messages["messages"].append(formatted_response)
            return {
                "messages": messages["messages"],
                "stream": stream,
                "session_state": session_state,
                "context": context,
            }

        simulator = AdversarialSimulator(azure_ai_project=azure_ai_project)

        outputs = asyncio.run(
            simulator(
                scenario=AdversarialScenario.ADVERSARIAL_QA,
                max_conversation_turns=1,
                max_simulation_results=1,
                target=callback,
                api_call_retry_limit=3,
                api_call_retry_sleep_sec=1,
                api_call_delay_sec=30,
                concurrent_async_task=1,
            )
        )
        assert len(outputs) == 1
        # assert topic and target_population is not present in outpts[0]["scenario_parameters"]
        assert "topic" not in outputs[0]["template_parameters"]
        assert "target_population" not in outputs[0]["template_parameters"]

    def test_adv_conversation_sim_responds_with_responses(self, azure_cred, project_scope):
        os.environ.pop("RAI_SVC_URL", None)
        from promptflow.evals.synthetic import AdversarialScenario, AdversarialSimulator

        azure_ai_project = {
            "subscription_id": project_scope["subscription_id"],
            "resource_group_name": project_scope["resource_group_name"],
            "project_name": project_scope["project_name"],
            "credential": azure_cred,
        }

        async def callback(
            messages: List[Dict], stream: bool = False, session_state: Any = None, context: Dict[str, Any] = None
        ) -> dict:
            question = messages["messages"][0]["content"]

            formatted_response = {"content": question, "role": "assistant"}
            messages["messages"].append(formatted_response)
            return {
                "messages": messages["messages"],
                "stream": stream,
                "session_state": session_state,
                "context": context,
            }

        simulator = AdversarialSimulator(azure_ai_project=azure_ai_project)

        outputs = asyncio.run(
            simulator(
                scenario=AdversarialScenario.ADVERSARIAL_CONVERSATION,
                max_conversation_turns=2,
                max_simulation_results=1,
                target=callback,
                api_call_retry_limit=3,
                api_call_retry_sleep_sec=1,
                api_call_delay_sec=30,
                concurrent_async_task=1,
            )
        )
        assert len(outputs) == 1
        print(outputs)
        assert len(outputs[0]["messages"]) == 4

    def test_adv_summarization_sim_responds_with_responses(self, azure_cred, project_scope):
        os.environ.pop("RAI_SVC_URL", None)
        from promptflow.evals.synthetic import AdversarialScenario, AdversarialSimulator

        azure_ai_project = {
            "subscription_id": project_scope["subscription_id"],
            "resource_group_name": project_scope["resource_group_name"],
            "project_name": project_scope["project_name"],
            "credential": azure_cred,
        }

        async def callback(
            messages: List[Dict], stream: bool = False, session_state: Any = None, context: Dict[str, Any] = None
        ) -> dict:
            question = messages["messages"][0]["content"]

            formatted_response = {"content": question, "role": "assistant"}
            messages["messages"].append(formatted_response)
            return {
                "messages": messages["messages"],
                "stream": stream,
                "session_state": session_state,
                "context": context,
            }

        simulator = AdversarialSimulator(azure_ai_project=azure_ai_project)

        outputs = asyncio.run(
            simulator(
                scenario=AdversarialScenario.ADVERSARIAL_SUMMARIZATION,
                max_conversation_turns=1,
                max_simulation_results=1,
                target=callback,
                api_call_retry_limit=3,
                api_call_retry_sleep_sec=1,
                api_call_delay_sec=30,
                concurrent_async_task=1,
            )
        )
        print(outputs.to_json_lines())
        print("*****************************")
        assert len(outputs) == 1

    def test_adv_summarization_jailbreak_sim_responds_with_responses(self, azure_cred, project_scope):
        os.environ.pop("RAI_SVC_URL", None)
        from promptflow.evals.synthetic import AdversarialScenario, AdversarialSimulator

        azure_ai_project = {
            "subscription_id": project_scope["subscription_id"],
            "resource_group_name": project_scope["resource_group_name"],
            "project_name": project_scope["project_name"],
            "credential": azure_cred,
        }

        async def callback(
            messages: List[Dict], stream: bool = False, session_state: Any = None, context: Dict[str, Any] = None
        ) -> dict:
            question = messages["messages"][0]["content"]

            formatted_response = {"content": question, "role": "assistant"}
            messages["messages"].append(formatted_response)
            return {
                "messages": messages["messages"],
                "stream": stream,
                "session_state": session_state,
                "context": context,
            }

        simulator = AdversarialSimulator(azure_ai_project=azure_ai_project)

        outputs = asyncio.run(
            simulator(
                scenario=AdversarialScenario.ADVERSARIAL_SUMMARIZATION,
                max_conversation_turns=1,
                max_simulation_results=1,
                target=callback,
                api_call_retry_limit=3,
                api_call_retry_sleep_sec=1,
                api_call_delay_sec=30,
                concurrent_async_task=1,
                jailbreak=True,
            )
        )
        print(outputs.to_json_lines())
        print("*****************************")
        assert len(outputs) == 1
