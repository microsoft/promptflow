import asyncio
import os
from typing import Any, Dict, List

import pytest

from promptflow.recording.record_mode import is_replay


@pytest.mark.usefixtures("recording_injection")
@pytest.mark.azuretest
class TestAdvSimulator:
    @pytest.mark.usefixtures("vcr_recording")
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

    @pytest.mark.usefixtures("vcr_recording")
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

    @pytest.mark.usefixtures("vcr_recording")
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
        assert len(outputs[0]["messages"]) == 4

    @pytest.mark.usefixtures("vcr_recording")
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
        assert len(outputs) == 1

    @pytest.mark.usefixtures("vcr_recording")
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
                _jailbreak_type="upia",
            )
        )
        assert len(outputs) == 1

    @pytest.mark.usefixtures("vcr_recording")
    def test_adv_rewrite_sim_responds_with_responses(self, azure_cred, project_scope):
        os.environ.pop("RAI_SVC_URL", None)
        from promptflow.evals.synthetic import AdversarialScenario, AdversarialSimulator

        azure_ai_project = {
            "subscription_id": project_scope["subscription_id"],
            "resource_group_name": project_scope["resource_group_name"],
            "project_name": project_scope["project_name"],
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

        simulator = AdversarialSimulator(azure_ai_project=azure_ai_project, credential=azure_cred)

        outputs = asyncio.run(
            simulator(
                scenario=AdversarialScenario.ADVERSARIAL_REWRITE,
                max_conversation_turns=1,
                max_simulation_results=1,
                target=callback,
                api_call_retry_limit=3,
                api_call_retry_sleep_sec=1,
                api_call_delay_sec=30,
                concurrent_async_task=1,
                _jailbreak_type="upia",
            )
        )
        assert len(outputs) == 1

    @pytest.mark.skipif(
        not is_replay(), reason="API not fully released yet. Don't run in live mode unless connected to INT."
    )
    @pytest.mark.usefixtures("vcr_recording")
    def test_adv_protected_matierial_sim_responds_with_responses(self, azure_cred, project_scope):
        os.environ.pop("RAI_SVC_URL", None)
        from promptflow.evals.synthetic import AdversarialScenario, AdversarialSimulator

        azure_ai_project = {
            "subscription_id": project_scope["subscription_id"],
            "resource_group_name": project_scope["resource_group_name"],
            "project_name": project_scope["project_name"],
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

        simulator = AdversarialSimulator(azure_ai_project=azure_ai_project, credential=azure_cred)

        outputs = asyncio.run(
            simulator(
                scenario=AdversarialScenario.ADVERSARIAL_CONTENT_PROTECTED_MATERIAL,
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

    @pytest.mark.skipif(
        not is_replay(), reason="API not fully released yet. Don't run in live mode unless connected to INT."
    )
    @pytest.mark.usefixtures("vcr_recording")
    def test_adv_eci_sim_responds_with_responses(self, azure_cred, project_scope):
        os.environ.pop("RAI_SVC_URL", None)
        from promptflow.evals.synthetic import AdversarialSimulator
        from promptflow.evals.synthetic.adversarial_scenario import _UnstableAdversarialScenario

        azure_ai_project = {
            "subscription_id": project_scope["subscription_id"],
            "resource_group_name": project_scope["resource_group_name"],
            "project_name": project_scope["project_name"],
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

        simulator = AdversarialSimulator(azure_ai_project=azure_ai_project, credential=azure_cred)

        outputs = asyncio.run(
            simulator(
                scenario=_UnstableAdversarialScenario.ECI,
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

    @pytest.mark.skipif(
        not is_replay(), reason="API not fully released yet. Don't run in live mode unless connected to INT."
    )
    @pytest.mark.skipif(
        is_replay(), reason="Test recording is polluted with telemetry data and fails in playback mode."
    )
    @pytest.mark.usefixtures("vcr_recording")
    def test_adv_xpia_sim_responds_with_responses(self, azure_cred, project_scope):
        os.environ.pop("RAI_SVC_URL", None)
        from promptflow.evals.synthetic import AdversarialScenario, IndirectAttackSimulator

        azure_ai_project = {
            "subscription_id": project_scope["subscription_id"],
            "resource_group_name": project_scope["resource_group_name"],
            "project_name": project_scope["project_name"],
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

        simulator = IndirectAttackSimulator(azure_ai_project=azure_ai_project, credential=azure_cred)

        outputs = asyncio.run(
            simulator(
                scenario=AdversarialScenario.ADVERSARIAL_INDIRECT_JAILBREAK,
                max_conversation_turns=1,
                max_simulation_results=1,
                target=callback,
            )
        )
        assert len(outputs) == 1

    @pytest.mark.skipif(
        is_replay(), reason="Something is instable/inconsistent in the recording. Fails in playback mode."
    )
    @pytest.mark.usefixtures("vcr_recording")
    def test_adv_sim_order_randomness_with_jailbreak(self, azure_cred, project_scope):
        os.environ.pop("RAI_SVC_URL", None)
        from promptflow.evals.synthetic import AdversarialScenario, AdversarialSimulator

        azure_ai_project = {
            "subscription_id": project_scope["subscription_id"],
            "resource_group_name": project_scope["resource_group_name"],
            "project_name": project_scope["project_name"],
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

        simulator = AdversarialSimulator(azure_ai_project=azure_ai_project, credential=azure_cred)

        outputs1 = asyncio.run(
            simulator(
                scenario=AdversarialScenario.ADVERSARIAL_REWRITE,
                max_conversation_turns=1,
                max_simulation_results=1,
                target=callback,
                api_call_retry_limit=3,
                api_call_retry_sleep_sec=1,
                api_call_delay_sec=30,
                concurrent_async_task=1,
                _jailbreak_type="upia",
                randomization_seed=1,
            )
        )

        outputs2 = asyncio.run(
            simulator(
                scenario=AdversarialScenario.ADVERSARIAL_REWRITE,
                max_conversation_turns=1,
                max_simulation_results=1,
                target=callback,
                api_call_retry_limit=3,
                api_call_retry_sleep_sec=1,
                api_call_delay_sec=30,
                concurrent_async_task=1,
                _jailbreak_type="upia",
                randomization_seed=1,
            )
        )

        outputs3 = asyncio.run(
            simulator(
                scenario=AdversarialScenario.ADVERSARIAL_REWRITE,
                max_conversation_turns=1,
                max_simulation_results=1,
                target=callback,
                api_call_retry_limit=3,
                api_call_retry_sleep_sec=1,
                api_call_delay_sec=30,
                concurrent_async_task=1,
                _jailbreak_type="upia",
                randomization_seed=2,
            )
        )
        # Make sure that outputs 1 and 2 are identical, but not identical to 3
        assert outputs1[0]["messages"][0] == outputs2[0]["messages"][0]
        assert outputs1[0]["messages"][0] != outputs3[0]["messages"][0]

    @pytest.mark.skipif(
        is_replay(), reason="Something is instable/inconsistent in the recording. Fails in playback mode."
    )
    @pytest.mark.usefixtures("vcr_recording")
    def test_adv_sim_order_randomness(self, azure_cred, project_scope):
        os.environ.pop("RAI_SVC_URL", None)
        from promptflow.evals.synthetic import AdversarialScenario, AdversarialSimulator

        azure_ai_project = {
            "subscription_id": project_scope["subscription_id"],
            "resource_group_name": project_scope["resource_group_name"],
            "project_name": project_scope["project_name"],
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

        simulator = AdversarialSimulator(azure_ai_project=azure_ai_project, credential=azure_cred)

        outputs1 = asyncio.run(
            simulator(
                scenario=AdversarialScenario.ADVERSARIAL_REWRITE,
                max_conversation_turns=1,
                max_simulation_results=1,
                target=callback,
                api_call_retry_limit=3,
                api_call_retry_sleep_sec=1,
                api_call_delay_sec=30,
                concurrent_async_task=1,
                randomization_seed=1,
            )
        )

        outputs2 = asyncio.run(
            simulator(
                scenario=AdversarialScenario.ADVERSARIAL_REWRITE,
                max_conversation_turns=1,
                max_simulation_results=1,
                target=callback,
                api_call_retry_limit=3,
                api_call_retry_sleep_sec=1,
                api_call_delay_sec=30,
                concurrent_async_task=1,
                randomization_seed=1,
            )
        )

        outputs3 = asyncio.run(
            simulator(
                scenario=AdversarialScenario.ADVERSARIAL_REWRITE,
                max_conversation_turns=1,
                max_simulation_results=1,
                target=callback,
                api_call_retry_limit=3,
                api_call_retry_sleep_sec=1,
                api_call_delay_sec=30,
                concurrent_async_task=1,
                randomization_seed=2,
            )
        )
        # Make sure that outputs 1 and 2 are identical, but not identical to 3
        assert outputs1[0]["messages"][0] == outputs2[0]["messages"][0]
        assert outputs1[0]["messages"][0] != outputs3[0]["messages"][0]

    @pytest.mark.skipif(
        is_replay(), reason="Something is instable/inconsistent in the recording. Fails in playback mode."
    )
    @pytest.mark.usefixtures("vcr_recording")
    def test_jailbreak_sim_order_randomness(self, azure_cred, project_scope):
        os.environ.pop("RAI_SVC_URL", None)
        from promptflow.evals.synthetic import AdversarialScenario, DirectAttackSimulator

        azure_ai_project = {
            "subscription_id": project_scope["subscription_id"],
            "resource_group_name": project_scope["resource_group_name"],
            "project_name": project_scope["project_name"],
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

        simulator = DirectAttackSimulator(azure_ai_project=azure_ai_project, credential=azure_cred)

        outputs1 = asyncio.run(
            simulator(
                scenario=AdversarialScenario.ADVERSARIAL_REWRITE,
                max_conversation_turns=1,
                max_simulation_results=1,
                target=callback,
                api_call_retry_limit=3,
                api_call_retry_sleep_sec=1,
                api_call_delay_sec=30,
                concurrent_async_task=1,
                randomization_seed=1,
            )
        )

        outputs2 = asyncio.run(
            simulator(
                scenario=AdversarialScenario.ADVERSARIAL_REWRITE,
                max_conversation_turns=1,
                max_simulation_results=1,
                target=callback,
                api_call_retry_limit=3,
                api_call_retry_sleep_sec=1,
                api_call_delay_sec=30,
                concurrent_async_task=1,
                randomization_seed=1,
            )
        )

        outputs3 = asyncio.run(
            simulator(
                scenario=AdversarialScenario.ADVERSARIAL_REWRITE,
                max_conversation_turns=1,
                max_simulation_results=1,
                target=callback,
                api_call_retry_limit=3,
                api_call_retry_sleep_sec=1,
                api_call_delay_sec=30,
                concurrent_async_task=1,
                randomization_seed=2,
            )
        )
        # Make sure the regular prompt exists within the jailbroken equivalent, but also that they aren't identical.
        outputs1["regular"][0]["messages"][0]["content"] in outputs1["jailbreak"][0]["messages"][0]["content"]
        outputs1["regular"][0]["messages"][0]["content"] != outputs1["jailbreak"][0]["messages"][0]["content"]
        # Check that outputs1 and outputs2 are identical, but not identical to outputs3
        outputs1["regular"][0]["messages"][0]["content"] == outputs2["regular"][0]["messages"][0]["content"]
        outputs1["jailbreak"][0]["messages"][0]["content"] == outputs2["jailbreak"][0]["messages"][0]["content"]
        outputs1["regular"][0]["messages"][0]["content"] != outputs3["regular"][0]["messages"][0]["content"]
        outputs1["jailbreak"][0]["messages"][0]["content"] != outputs3["jailbreak"][0]["messages"][0]["content"]
        # Check that outputs3 has the same equivalency as outputs1, even without a provided seed.
        outputs3["regular"][0]["messages"][0]["content"] in outputs3["jailbreak"][0]["messages"][0]["content"]
        outputs3["regular"][0]["messages"][0]["content"] != outputs3["jailbreak"][0]["messages"][0]["content"]
