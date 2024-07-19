from unittest.mock import MagicMock

import pytest

from promptflow.evals.evaluators import FluencyEvaluator


async def fluency_async_mock():
    return "1"


@pytest.mark.usefixtures("mock_model_config")
@pytest.mark.unittest
class TestBuiltInEvaluators:
    def test_fluency_evaluator(self, mock_model_config):
        fluency_eval = FluencyEvaluator(model_config=mock_model_config)
        fluency_eval._async_evaluator._flow = MagicMock(return_value=fluency_async_mock())

        score = fluency_eval(question="What is the capital of Japan?", answer="The capital of Japan is Tokyo.")

        assert score is not None
        assert score["gpt_fluency"] == 1

    def test_fluency_evaluator_non_string_inputs(self, mock_model_config):
        fluency_eval = FluencyEvaluator(model_config=mock_model_config)
        fluency_eval._async_evaluator._flow = MagicMock(return_value=fluency_async_mock())

        score = fluency_eval(question={"foo": 1}, answer={"bar": "2"})

        assert score is not None
        assert score["gpt_fluency"] == 1

    def test_fluency_evaluator_empty_string(self, mock_model_config):
        fluency_eval = FluencyEvaluator(model_config=mock_model_config)
        fluency_eval._async_evaluator._flow = MagicMock(return_value=fluency_async_mock())

        with pytest.raises(ValueError) as exc_info:
            fluency_eval(question="What is the capital of Japan?", answer=None)

        assert "Both 'question' and 'answer' must be non-empty strings." in exc_info.value.args[0]

        with pytest.raises(ValueError) as exc_info:
            fluency_eval(question="What is the capital of Japan?", answer="")

        assert "Both 'question' and 'answer' must be non-empty strings." in exc_info.value.args[0]
