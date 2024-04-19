import pytest

from promptflow.evals.evaluators import GroundednessEvaluator


@pytest.mark.usefixtures("model_config", "recording_injection")
@pytest.mark.e2etest
class TestQualityEvaluators:
    def test_groundedness_evaluator(self, model_config):
        groundedness_eval = GroundednessEvaluator(model_config)
        score = groundedness_eval(
            answer="The Alpine Explorer Tent is the most waterproof.",
            context="From the our product list, the alpine explorer tent is the most waterproof. The Adventure Dining "
            "Table has higher weight.",
        )
        assert score is not None
        assert score["gpt_groundedness"] > 1.0
