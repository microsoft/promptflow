import pytest

from promptflow.evals.evaluators import ContentSafetyChatEvaluator


@pytest.mark.usefixtures("mock_project_scope")
@pytest.mark.unittest
class TestChatEvaluator:
    def test_conversation_validation_normal(self, mock_project_scope):
        conversation = [
            {"role": "user", "content": "What is the value of 2 + 2?"},
            {
                "role": "assistant",
                "content": "2 + 2 = 4",
            },
            {"role": "user", "content": "What is the capital of Japan?"},
            {
                "role": "assistant",
                "content": "The capital of Japan is Tokyo.",
            },
        ]

        chat_eval = ContentSafetyChatEvaluator(mock_project_scope)
        chat_eval._evaluators = []

        chat_eval(conversation=conversation)

    def test_conversation_validation_missing_role(self, mock_project_scope):
        conversation = [
            {"role": "user", "content": "question 1"},
            {"content": "answer 1"},
        ]

        chat_eval = ContentSafetyChatEvaluator(mock_project_scope)
        chat_eval._evaluators = []

        with pytest.raises(ValueError) as e:
            chat_eval(conversation=conversation)
        assert str(e.value) == "Each turn in 'conversation' must have 'role' and 'content' keys. Turn number: 2"

    def test_conversation_validation_question_answer_not_paired(self, mock_project_scope):
        conversation = [
            {"role": "user", "content": "question 1"},
            {"role": "assistant", "content": "answer 1"},
            {"role": "assistant", "content": "answer 2"},
        ]

        chat_eval = ContentSafetyChatEvaluator(mock_project_scope)
        chat_eval._evaluators = []

        with pytest.raises(ValueError) as e:
            chat_eval(conversation=conversation)
        assert str(e.value) == "Expected role user but got assistant. Turn number: 3"

    def test_per_turn_results_aggregation(self, mock_project_scope):
        chat_eval = ContentSafetyChatEvaluator(mock_project_scope)

        per_turn_results = [
            {
                "violence": "Very low",
                "violence_reason": "reason1",
                "violence_score": 0.0,
            },
            {
                "violence": "Very low",
                "violence_reason": "reason2",
                "violence_score": 1.0,
            },
        ]
        aggregated = chat_eval._aggregate_results(per_turn_results)
        assert aggregated == {
            "violence": "Very low",
            "violence_score": 0.5,
            "evaluation_per_turn": {
                "violence": {
                    "severity": ["Very low", "Very low"],
                    "score": [0.0, 1.0],
                    "reason": ["reason1", "reason2"],
                }
            },
        }
