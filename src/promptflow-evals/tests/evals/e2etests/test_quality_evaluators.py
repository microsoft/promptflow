import pytest

from promptflow.evals.evaluators import ChatEvaluator


@pytest.mark.usefixtures("model_config", "recording_injection")
@pytest.mark.e2etest
class TestQualityEvaluators:
    def test_composite_evaluator_chat(self, model_config):
        eval_last_turn = False
        chat_eval = ChatEvaluator(model_config, eval_last_turn=eval_last_turn, parallel=False)

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
