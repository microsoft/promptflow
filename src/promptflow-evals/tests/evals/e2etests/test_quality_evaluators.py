import pytest

from promptflow.connections import AzureOpenAIConnection
from promptflow.evals.evaluators import GroundednessEvaluator


@pytest.mark.usefixtures("dev_connections", "recording_injection")
@pytest.mark.e2etest
class TestQualityEvaluators:
    def test_groundedness_evaluator(self, dev_connections):
        model_config = self._get_model_config(dev_connections)
        groundedness_eval = GroundednessEvaluator(model_config, "gpt-4")
        score = groundedness_eval(
            answer="The Alpine Explorer Tent is the most waterproof.",
            context="From the our product list, the alpine explorer tent is the most waterproof. The Adventure Dining "
            "Table has higher weight.",
        )
        assert score is not None
        assert score["gpt_groundedness"] > 1.0

    def _get_model_config(self, dev_connections):
        conn_name = "azure_open_ai_connection"
        if conn_name not in dev_connections:
            raise ValueError(f"Connection '{conn_name}' not found in dev connections.")

        model_config = AzureOpenAIConnection(**dev_connections[conn_name]["value"])

        return model_config
