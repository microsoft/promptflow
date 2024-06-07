import pytest

from promptflow.evals.evaluators import (
    ChatEvaluator,
    ContentSafetyChatEvaluator,
    ContentSafetyEvaluator,
    FluencyEvaluator,
    QAEvaluator,
    ViolenceEvaluator,
)


@pytest.mark.usefixtures("recording_injection", "vcr_recording")
@pytest.mark.e2etest
class TestBuiltInEvaluators:
    def test_individual_evaluator_prompt_based(self, model_config):
        eval_fn = FluencyEvaluator(model_config)
        score = eval_fn(
            question="What is the capital of Japan?",
            answer="The capital of Japan is Tokyo.",
        )
        assert score is not None
        assert score["gpt_fluency"] > 1.0

    def test_individual_evaluator_prompt_based_with_dict_input(self, model_config):
        eval_fn = FluencyEvaluator(model_config)
        score = eval_fn(
            question={"foo": "1"},
            answer={"bar": 2},
        )
        assert score is not None
        assert score["gpt_fluency"] > 0.0

    def test_individual_evaluator_service_based(self, project_scope, azure_cred):
        eval_fn = ViolenceEvaluator(project_scope, azure_cred)
        score = eval_fn(
            question="What is the capital of Japan?",
            answer="The capital of Japan is Tokyo.",
        )
        assert score is not None
        assert score["violence"] == "Very low"
        assert score["violence_score"] < 1.0
        assert score["violence_reason"], "violence_reason must not be None or empty."

    @pytest.mark.parametrize("parallel", [False, True])
    def test_composite_evaluator_qa(self, model_config, parallel):
        qa_eval = QAEvaluator(model_config, parallel=parallel)
        score = qa_eval(
            question="Tokyo is the capital of which country?",
            answer="Japan",
            context="Tokyo is the capital of Japan.",
            ground_truth="Japan",
        )

        assert score is not None
        assert score["gpt_groundedness"] > 0.0
        assert score["gpt_relevance"] > 0.0
        assert score["gpt_coherence"] > 0.0
        assert score["gpt_fluency"] > 0.0
        assert score["gpt_similarity"] > 0.0
        assert score["f1_score"] > 0.0

    def test_composite_evaluator_content_safety(self, project_scope, azure_cred):
        safety_eval = ContentSafetyEvaluator(project_scope, parallel=False, credential=azure_cred)
        score = safety_eval(
            question="Tokyo is the capital of which country?",
            answer="Japan",
        )

        assert score is not None
        assert score["violence"] == "Very low"
        assert score["violence_score"] < 1.0
        assert score["violence_reason"], "violence_reason must not be None or empty."
        assert score["sexual"] == "Very low"
        assert score["sexual_score"] < 1.0
        assert score["sexual_reason"], "sexual_reason must not be None or empty."
        assert score["self_harm"] == "Very low"
        assert score["self_harm_score"] < 1.0
        assert score["self_harm_reason"], "self_harm_reason must not be None or empty."
        assert score["hate_unfairness"] == "Very low"
        assert score["hate_unfairness_score"] < 1.0
        assert score["hate_unfairness_reason"], "hate_unfairness_reason must not be None or empty."

    @pytest.mark.parametrize(
        "eval_last_turn, parallel",
        [
            (False, True),
            (True, True),
        ],
    )
    def test_composite_evaluator_chat(self, model_config, eval_last_turn, parallel):
        chat_eval = ChatEvaluator(model_config, eval_last_turn=eval_last_turn, parallel=parallel)

        conversation = [
            {"role": "user", "content": "What is the value of 2 + 2?"},
            {
                "role": "assistant",
                "content": "2 + 2 = 4",
                "context": {
                    "citations": [{"id": "doc.md", "content": "Information about additions: 1 + 2 = 3, 2 + 2 = 4"}]
                },
            },
            {"role": "user", "content": "What is the capital of Japan?"},
            {
                "role": "assistant",
                "content": "The capital of Japan is Tokyo.",
                "context": {
                    "citations": [
                        {
                            "id": "doc.md",
                            "content": "Tokyo is Japan's capital, known for its blend of traditional culture and \
                                technological"
                            "advancements.",
                        }
                    ]
                },
            },
        ]

        score = chat_eval(conversation=conversation)

        assert score is not None
        assert score["gpt_groundedness"] > 0.0
        assert score["gpt_relevance"] > 0.0
        assert score["gpt_coherence"] > 0.0
        assert score["gpt_fluency"] > 0.0
        assert score["gpt_retrieval"] > 0.0
        assert score["evaluation_per_turn"] is not None

        turn_count = 1 if eval_last_turn else 2
        assert score["evaluation_per_turn"]["gpt_groundedness"] is not None
        assert len(score["evaluation_per_turn"]["gpt_groundedness"]["score"]) == turn_count

        assert score["evaluation_per_turn"]["gpt_relevance"] is not None
        assert len(score["evaluation_per_turn"]["gpt_relevance"]["score"]) == turn_count

        assert score["evaluation_per_turn"]["gpt_coherence"] is not None
        assert len(score["evaluation_per_turn"]["gpt_coherence"]["score"]) == turn_count

        assert score["evaluation_per_turn"]["gpt_fluency"] is not None
        assert len(score["evaluation_per_turn"]["gpt_fluency"]["score"]) == turn_count

        assert score["evaluation_per_turn"]["gpt_retrieval"] is not None
        assert len(score["evaluation_per_turn"]["gpt_retrieval"]["score"]) == turn_count

    @pytest.mark.parametrize(
        "eval_last_turn, parallel",
        [
            (False, False),
            (True, False),
        ],
    )
    def test_composite_evaluator_content_safety_chat(self, project_scope, eval_last_turn, parallel, azure_cred):
        chat_eval = ContentSafetyChatEvaluator(
            project_scope, eval_last_turn=eval_last_turn, parallel=parallel, credential=azure_cred
        )

        conversation = [
            {"role": "user", "content": "What is the value of 2 + 2?"},
            {
                "role": "assistant",
                "content": "2 + 2 = 4",
                "context": {
                    "citations": [{"id": "doc.md", "content": "Information about additions: 1 + 2 = 3, 2 + 2 = 4"}]
                },
            },
            {"role": "user", "content": "What is the capital of Japan?"},
            {
                "role": "assistant",
                "content": "The capital of Japan is Tokyo.",
                "context": {
                    "citations": [
                        {
                            "id": "doc.md",
                            "content": "Tokyo is Japan's capital, known for its blend of traditional culture and \
                                technological"
                            "advancements.",
                        }
                    ]
                },
            },
        ]

        score = chat_eval(conversation=conversation)

        assert score is not None
        assert score["violence"] == "Very low"
        assert score["violence_score"] < 1.0
        assert score["sexual"] == "Very low"
        assert score["sexual_score"] < 1.0
        assert score["self_harm"] == "Very low"
        assert score["self_harm_score"] < 1.0
        assert score["hate_unfairness"] == "Very low"
        assert score["hate_unfairness_score"] < 1.0

        assert score["evaluation_per_turn"] is not None

        turn_count = 1 if eval_last_turn else 2
        assert score["evaluation_per_turn"]["violence"] is not None
        assert len(score["evaluation_per_turn"]["violence"]["score"]) == turn_count
        assert len(score["evaluation_per_turn"]["violence"]["reason"]) == turn_count
        assert len(score["evaluation_per_turn"]["violence"]["severity"]) == turn_count

        assert score["evaluation_per_turn"]["sexual"] is not None
        assert len(score["evaluation_per_turn"]["sexual"]["score"]) == turn_count
        assert len(score["evaluation_per_turn"]["sexual"]["reason"]) == turn_count
        assert len(score["evaluation_per_turn"]["sexual"]["severity"]) == turn_count

        assert score["evaluation_per_turn"]["self_harm"] is not None
        assert len(score["evaluation_per_turn"]["self_harm"]["score"]) == turn_count
        assert len(score["evaluation_per_turn"]["self_harm"]["reason"]) == turn_count
        assert len(score["evaluation_per_turn"]["self_harm"]["severity"]) == turn_count

        assert score["evaluation_per_turn"]["hate_unfairness"] is not None
        assert len(score["evaluation_per_turn"]["hate_unfairness"]["score"]) == turn_count
        assert len(score["evaluation_per_turn"]["hate_unfairness"]["reason"]) == turn_count
        assert len(score["evaluation_per_turn"]["hate_unfairness"]["severity"]) == turn_count
