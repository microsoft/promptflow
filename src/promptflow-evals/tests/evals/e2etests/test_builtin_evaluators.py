import numpy as np
import pytest

from promptflow.evals.evaluators import (
    ChatEvaluator,
    CoherenceEvaluator,
    ContentSafetyChatEvaluator,
    ContentSafetyEvaluator,
    F1ScoreEvaluator,
    FluencyEvaluator,
    GroundednessEvaluator,
    HateUnfairnessEvaluator,
    QAEvaluator,
    RelevanceEvaluator,
    SelfHarmEvaluator,
    SexualEvaluator,
    SimilarityEvaluator,
    ViolenceEvaluator,
)
from promptflow.recording.record_mode import is_replay


@pytest.mark.usefixtures("recording_injection", "vcr_recording")
@pytest.mark.localtest
class TestBuiltInEvaluators:
    def test_quality_evaluator_fluency(self, model_config):
        eval_fn = FluencyEvaluator(model_config)
        score = eval_fn(
            question="What is the capital of Japan?",
            answer="The capital of Japan is Tokyo.",
        )
        assert score is not None
        assert score["gpt_fluency"] > 1.0

    def test_quality_evaluator_coherence(self, model_config):
        eval_fn = CoherenceEvaluator(model_config)
        score = eval_fn(
            question="What is the capital of Japan?",
            answer="The capital of Japan is Tokyo.",
        )
        assert score is not None
        assert score["gpt_coherence"] > 1.0

    def test_quality_evaluator_similarity(self, model_config):
        eval_fn = SimilarityEvaluator(model_config)
        score = eval_fn(
            question="What is the capital of Japan?",
            answer="The capital of Japan is Tokyo.",
            ground_truth="Tokyo is Japan's capital.",
        )
        assert score is not None
        assert score["gpt_similarity"] > 1.0

    def test_quality_evaluator_groundedness(self, model_config):
        eval_fn = GroundednessEvaluator(model_config)
        score = eval_fn(
            answer="The capital of Japan is Tokyo.",
            context="Tokyo is Japan's capital.",
        )
        assert score is not None
        assert score["gpt_groundedness"] > 1.0

    def test_quality_evaluator_relevance(self, model_config):
        eval_fn = RelevanceEvaluator(model_config)
        score = eval_fn(
            question="What is the capital of Japan?",
            answer="The capital of Japan is Tokyo.",
            context="Tokyo is Japan's capital.",
        )
        assert score is not None
        assert score["gpt_relevance"] > 1.0

    def test_quality_evaluator_f1_score(self):
        eval_fn = F1ScoreEvaluator()
        score = eval_fn(
            answer="The capital of Japan is Tokyo.",
            ground_truth="Tokyo is Japan's capital.",
        )
        assert score is not None
        assert score["f1_score"] > 0.0

    def test_quality_evaluator_prompt_based_with_dict_input(self, model_config):
        eval_fn = FluencyEvaluator(model_config)
        score = eval_fn(
            question={"foo": "1"},
            answer={"bar": 2},
        )
        assert score is not None
        assert score["gpt_fluency"] > 0.0

    def test_content_safety_evaluator_violence(self, project_scope, azure_cred):
        eval_fn = ViolenceEvaluator(project_scope, azure_cred)
        score = eval_fn(
            question="What is the capital of Japan?",
            answer="The capital of Japan is Tokyo.",
        )
        assert score is not None
        assert score["violence"] == "Very low"
        assert score["violence_score"] < 1.0
        assert score["violence_reason"], "violence_reason must not be None or empty."

    def test_content_safety_evaluator_sexual(self, project_scope, azure_cred):
        eval_fn = SexualEvaluator(project_scope, azure_cred)
        score = eval_fn(
            question="What is the capital of Japan?",
            answer="The capital of Japan is Tokyo.",
        )
        assert score is not None
        assert score["sexual"] == "Very low"
        assert score["sexual_score"] < 1.0
        assert score["sexual_reason"], "sexual_reason must not be None or empty."

    def test_content_safety_evaluator_self_harm(self, project_scope, azure_cred):
        eval_fn = SelfHarmEvaluator(project_scope, azure_cred)
        score = eval_fn(
            question="What is the capital of Japan?",
            answer="The capital of Japan is Tokyo.",
        )
        assert score is not None
        assert score["self_harm"] == "Very low"
        assert score["self_harm_score"] < 1.0
        assert score["self_harm_reason"], "self_harm_reason must not be None or empty."

    def test_content_safety_evaluator_hate_unfairness(self, project_scope, azure_cred):
        eval_fn = HateUnfairnessEvaluator(project_scope, azure_cred)
        score = eval_fn(
            question="What is the capital of Japan?",
            answer="The capital of Japan is Tokyo.",
        )
        assert score is not None
        assert score["hate_unfairness"] == "Very low"
        assert score["hate_unfairness_score"] < 1.0
        assert score["hate_unfairness_reason"], "hate_unfairness_reason must not be None or empty."

    def test_content_safety_service_unavailable(self, project_scope, azure_cred):
        eval_fn = ViolenceEvaluator(project_scope, azure_cred)
        # Doing this is replay mode breaks causes mismatch between scrubbed recordings
        # and the actual request made.
        # Using not is_replay() because is_live doesn't apply to recording mode?
        if not is_replay():
            # Warning, live testing fails due to unstable region.
            # We need a use a new region.
            project_scope["project_name"] = "pf-evals-ws-westus2"

        with pytest.raises(Exception) as exc_info:
            score = eval_fn(
                question="What is the capital of Japan?",
                answer="The capital of Japan is Tokyo.",
            )
            print(score)

        assert "RAI service is not available in this region" in exc_info._excinfo[1].args[0]

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

    @pytest.mark.skipif(True, reason="Team-wide OpenAI Key unavailable, this can't be tested broadly yet.")
    @pytest.mark.parametrize("parallel", [False, True])
    def test_composite_evaluator_qa_with_openai_config(self, non_azure_openai_model_config, parallel):
        # openai_config as in "not azure openai"
        qa_eval = QAEvaluator(non_azure_openai_model_config, parallel=parallel)
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

    def test_composite_evaluator_qa_for_nans(self, model_config):
        qa_eval = QAEvaluator(model_config)
        # Test Q/A below would cause NaNs in the evaluation metrics before the fix.
        score = qa_eval(question="This's the color?", answer="Black", ground_truth="gray", context="gray")

        assert score["gpt_groundedness"] is not np.nan
        assert score["gpt_relevance"] is not np.nan
        assert score["gpt_coherence"] is not np.nan
        assert score["gpt_fluency"] is not np.nan
        assert score["gpt_similarity"] is not np.nan

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
