import pytest
from promptflow.evals.evaluators import ChatEvaluator
from promptflow.entities import AzureOpenAIConnection


@pytest.mark.unittest
class TestChatEvaluator:
    def test_conversation_validation_normal(self):
        model_config = AzureOpenAIConnection(
            api_base="mocked_endpoint",
            api_key="mocked_key",
            api_type="azure",
        )

        conversation = [
            {"role": "user", "content": "What is the value of 2 + 2?"},
            {"role": "assistant", "content": "2 + 2 = 4", "context": {
                "citations": [{"id": "doc.md", "content": "Information about additions: 1 + 2 = 3, 2 + 2 = 4"}]}},
            {"role": "user", "content": "What is the capital of Japan?"},
            {"role": "assistant", "content": "The capital of Japan is Tokyo.", "context": {"citations": [
                {"id": "doc.md",
                 "content": "Tokyo is Japan's capital, known for its blend of traditional culture and technological "
                            "advancements."}]}},
        ]

        chat_eval = ChatEvaluator(model_config=model_config, deployment_name="gpt-4")
        chat_eval._non_rag_evaluators = []
        chat_eval._rag_evaluators = []

        chat_eval(conversation=conversation)

    def test_conversation_validation_missing_role(self):
        model_config = AzureOpenAIConnection(
            api_base="mocked_endpoint",
            api_key="mocked_key",
            api_type="azure",
        )

        conversation = [
            {"role": "user", "content": "question 1"},
            {"content": "answer 1"},
        ]

        chat_eval = ChatEvaluator(model_config=model_config, deployment_name="gpt-4")
        chat_eval._non_rag_evaluators = []
        chat_eval._rag_evaluators = []

        with pytest.raises(ValueError) as e:
            chat_eval(conversation=conversation)
        assert str(e.value) == "Each turn in 'conversation' must have 'role' and 'content' keys. Turn number: 2"

    def test_conversation_validation_question_answer_not_paired(self):
        model_config = AzureOpenAIConnection(
            api_base="mocked_endpoint",
            api_key="mocked_key",
            api_type="azure",
        )

        conversation = [
            {"role": "user", "content": "question 1"},
            {"role": "assistant", "content": "answer 1"},
            {"role": "assistant", "content": "answer 2"},
        ]

        chat_eval = ChatEvaluator(model_config=model_config, deployment_name="gpt-4")
        chat_eval._non_rag_evaluators = []
        chat_eval._rag_evaluators = []

        with pytest.raises(ValueError) as e:
            chat_eval(conversation=conversation)
        assert str(e.value) == "Expected role user but got assistant. Turn number: 3"

    def test_conversation_validation_invalid_citations(self):
        model_config = AzureOpenAIConnection(
            api_base="mocked_endpoint",
            api_key="mocked_key",
            api_type="azure",
        )

        conversation = [
            {"role": "user", "content": "question 1"},
            {"role": "assistant", "content": "answer 1", "context": {"citations": "invalid"}},
        ]

        chat_eval = ChatEvaluator(model_config=model_config, deployment_name="gpt-4")
        chat_eval._non_rag_evaluators = []
        chat_eval._rag_evaluators = []

        with pytest.raises(ValueError) as e:
            chat_eval(conversation=conversation)
        assert str(e.value) == "'citations' in context must be a list. Turn number: 2"

    def test_per_turn_results_aggregation(self):
        model_config = AzureOpenAIConnection(
            api_base="mocked_endpoint",
            api_key="mocked_key",
            api_type="azure",
        )
        chat_eval = ChatEvaluator(model_config=model_config, deployment_name="gpt-4")

        per_turn_results = [
            {
                "gpt_groundedness": 1.0,
                "gpt_groundedness_reason": "reason1",
                "gpt_fluency": 2.0,

            },
            {
                "gpt_groundedness": 3.0,
                "gpt_groundedness_reason": "reason2",
                "gpt_fluency": 4.0,
            },
        ]
        aggregated = chat_eval._aggregate_results(per_turn_results)
        assert aggregated == {
            "gpt_groundedness": 2.0,
            "gpt_fluency": 3.0,
            "evaluation_per_turn": {
                "gpt_groundedness": {"score": [1.0, 3.0], "reason": ["reason1", "reason2"]},
                "gpt_fluency": {"score": [2.0, 4.0]},
            }
        }
