# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
import pathlib

import pytest

from promptflow.evals.synthetic.qa import OutputStructure, QADataGenerator, QAType

API_BASE = ""
API_KEY = ""
DEPLOYMENT = ""
MODEL = ""


@pytest.mark.unittest
class TestDataGenerator:
    def test_extract_qa_from_response(self):
        response_text = """[Q]: What is Compute Instance?
[A]: Compute instance is ...
[Q]: Is CI different than Compute Cluster?
[A]: Yes.
[Q]: In what way?
[A]: It is different ... because ...
... these are the reasons.
   Here's one more reason ...
[Q]: Is K8s also a compute?
[A]: Yes.

[Q]: Question after space?
[A]: Answer after space.

"""
        expected_questions = [
            "What is Compute Instance?",
            "Is CI different than Compute Cluster?",
            "In what way?",
            "Is K8s also a compute?",
            "Question after space?",
        ]
        expected_answers = [
            "Compute instance is ...",
            "Yes.",
            "It is different ... because ...\n... these are the reasons.\n   Here's one more reason ...",
            "Yes.\n",
            "Answer after space.\n\n",
        ]
        model_config = dict(api_base=API_BASE, api_key=API_KEY, deployment=DEPLOYMENT, model=MODEL)
        qa_generator = QADataGenerator(model_config)
        questions, answers = qa_generator._parse_qa_from_response(response_text=response_text)
        for i, question in enumerate(questions):
            assert expected_questions[i] == question, "Question not equal"
        for i, answer in enumerate(answers):
            assert expected_answers[i] == answer, "Answer not equal"

    def test_unsupported_num_questions_for_summary(self):
        model_config = dict(api_base=API_BASE, api_key=API_KEY, deployment=DEPLOYMENT, model=MODEL)
        qa_generator = QADataGenerator(model_config)
        with pytest.raises(ValueError) as excinfo:
            qa_generator.generate("", QAType.SUMMARY, 10)
        assert str(excinfo.value) == "num_questions unsupported for Summary QAType"

    @pytest.mark.parametrize("num_questions", [0, -1])
    def test_invalid_num_questions(self, num_questions):
        model_config = dict(api_base=API_BASE, api_key=API_KEY, deployment=DEPLOYMENT, model=MODEL)
        qa_generator = QADataGenerator(model_config)
        with pytest.raises(ValueError) as excinfo:
            qa_generator.generate("", QAType.SHORT_ANSWER, num_questions)
        assert str(excinfo.value) == "num_questions must be an integer greater than zero"

    @pytest.mark.parametrize("qa_type", [QAType.CONVERSATION, QAType.SHORT_ANSWER])
    @pytest.mark.parametrize("structure", [OutputStructure.CHAT_PROTOCOL, OutputStructure.PROMPTFLOW])
    def test_export_format(self, qa_type, structure):
        questions = [
            "What is Compute Instance?",
            "Is CI different than Compute Cluster?",
            "In what way?",
            "Is K8s also a compute?",
            "Question after space?",
        ]
        answers = [
            "Compute instance is ...",
            "Yes.",
            "It is different ... because ...\n... these are the reasons.\n   Here's one more reason ...",
            "Yes.\n",
            "Answer after space.\n\n",
        ]

        model_config = dict(api_base=API_BASE, api_key=API_KEY, deployment=DEPLOYMENT, model=MODEL)
        qa_generator = QADataGenerator(model_config)
        qas = list(zip(questions, answers))
        filepath = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
        output_file = os.path.join(filepath, f"test_{qa_type.value}_{structure.value}.jsonl")
        qa_generator.export_to_file(output_file, qa_type, qas, structure)

        if qa_type == QAType.CONVERSATION and structure == OutputStructure.CHAT_PROTOCOL:
            filename = "generated_qa_chat_conv.jsonl"
        elif qa_type == QAType.CONVERSATION and structure == OutputStructure.PROMPTFLOW:
            filename = "generated_qa_pf_conv.jsonl"
        elif qa_type == QAType.SHORT_ANSWER and structure == OutputStructure.CHAT_PROTOCOL:
            filename = "generated_qa_chat_short.jsonl"
        elif qa_type == QAType.SHORT_ANSWER and structure == OutputStructure.PROMPTFLOW:
            filename = "generated_qa_pf_short.jsonl"

        expected_file = os.path.join(filepath, filename)

        try:
            with open(expected_file, "r") as json_file:
                expected_lines = list(json_file)

            with open(output_file, "r") as json_file:
                actual_lines = list(json_file)

            assert len(expected_lines) == len(actual_lines)

            for i in range(0, len(expected_lines)):
                assert expected_lines[i] == actual_lines[i]
        except Exception as e:
            # Still raise exception
            print(f"Exception encountered in test: {e}")
            raise
        finally:
            # clean up file
            os.remove(output_file)
