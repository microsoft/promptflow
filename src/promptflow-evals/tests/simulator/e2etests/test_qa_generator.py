import os

import pytest

from promptflow.evals.synthetic.qa import QADataGenerator, QAType


@pytest.mark.usefixtures("model_config", "recording_injection")
@pytest.mark.e2etest
class TestQAGenerator:
    def setup(self, model_config):
        os.environ["AZURE_OPENAI_ENDPOINT"] = model_config.azure_endpoint
        os.environ["AZURE_OPENAI_KEY"] = model_config.api_key
        text = (
            "Leonardo di ser Piero da Vinci (15 April 1452 - 2 May 1519) was an Italian "
            "polymath of the High Renaissance who was active as a painter, draughtsman, "
            "engineer, scientist, theorist, sculptor, and architect. While his fame "
            "initially rested on his achievements as a painter, he has also become known "
            "for his notebooks, in which he made drawings and notes on a variety of "
            "subjects, including anatomy, astronomy, botany, cartography, painting, and "
            "paleontology. Leonardo epitomized the Renaissance humanist ideal, and his "
            "collective works comprise a contribution to later generations of artists "
            "matched only by that of his younger contemporary Michelangelo."
        )
        return text

    def test_qa_generator_basic_conversation(self, model_config):
        model_name = "gpt-4"
        text = self.setup(model_config)
        model_config = dict(
            deployment=model_name,
            model=model_name,
            max_tokens=2000,
        )
        qa_generator = QADataGenerator(model_config=model_config)
        qa_type = QAType.CONVERSATION
        result = qa_generator.generate(text=text, qa_type=qa_type, num_questions=5)
        assert "question_answers" in result.keys()
        assert len(result["question_answers"]) == 5

    def test_qa_generator_basic_summary(self, model_config):
        model_name = "gpt-4"
        text = self.setup(model_config)
        model_config = dict(
            deployment=model_name,
            model=model_name,
            max_tokens=2000,
        )
        qa_generator = QADataGenerator(model_config=model_config)
        qa_type = QAType.SUMMARY
        result = qa_generator.generate(text=text, qa_type=qa_type)
        assert "question_answers" in result.keys()
        assert len(result["question_answers"]) == 1
        assert result["question_answers"][0][0].startswith("Write a summary in 100 words")
