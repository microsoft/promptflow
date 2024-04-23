import asyncio
import os

import pytest
from azure.ai.ml import MLClient
from azure.identity import DefaultAzureCredential

from promptflow.evals.synthetic.simulator.simulator import Simulator


@pytest.mark.usefixtures(
    "model_config", "recording_injection", "ml_client_config", "configure_default_azure_credential"
)
@pytest.mark.e2etest
class TestAdvSimulator:
    @pytest.mark.skip(reason="timed out after 10 seconds")
    def test_conversation(self, model_config, ml_client_config):
        os.environ["rai_svc_url"] = "https://int.api.azureml-test.ms"
        from openai import AsyncAzureOpenAI

        oai_client = AsyncAzureOpenAI(
            api_key=model_config.api_key,
            azure_endpoint=model_config.azure_endpoint,
            api_version="2023-12-01-preview",
        )
        ml_client = MLClient(
            credential=DefaultAzureCredential(),
            workspace_name=ml_client_config["project_name"],
            subscription_id=ml_client_config["subscription_id"],
            resource_group_name=ml_client_config["resource_group_name"],
        )
        ch_template = Simulator.get_template("adv_conversation")
        async_oai_chat_completion_fn = oai_client.chat.completions.create
        simulator = Simulator.from_fn(
            fn=async_oai_chat_completion_fn,
            ml_client=ml_client,
            model="gpt-4",
            max_tokens=300,
        )

        outputs = asyncio.run(
            simulator.simulate_async(
                template=ch_template,
                max_conversation_turns=5,
                api_call_delay_sec=60,
                max_simulation_results=1,
            )
        )

        in_json_line_format = outputs.to_json_lines()
        assert in_json_line_format is not None
        assert len(in_json_line_format) > 0
