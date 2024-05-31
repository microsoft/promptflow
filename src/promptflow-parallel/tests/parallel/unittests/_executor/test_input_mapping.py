# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from promptflow.parallel._executor.input_mapping import InputMapping
from promptflow.parallel._model import Row


@pytest.mark.unittest
def test_empty_mapping():
    with TemporaryDirectory() as input_dir, TemporaryDirectory() as side_input_dir:
        input_mapping = InputMapping(Path(input_dir), Path(side_input_dir), {})
        row = Row.from_dict({"field": "test"}, row_number=0)
        mapped = input_mapping.apply(row)

        assert mapped == row


@pytest.mark.unittest
def test_apply_input_mapping():
    mapping = {
        "question": "${data.question}",
        "groundtruth": "${data.answer}",
    }
    row = Row.from_dict({"answer": "I'm fine, thank you.", "question": "How are you?"}, row_number=0)
    with TemporaryDirectory() as input_dir, TemporaryDirectory() as side_input_dir:
        input_mapping = InputMapping(Path(input_dir), Path(side_input_dir), mapping)
        mapped = input_mapping.apply(row)

        assert mapped == {"question": "How are you?", "groundtruth": "I'm fine, thank you."}


@pytest.mark.unittest
def test_apply_input_mapping_with_side_input(save_jsonl):
    mapping = {
        "question": "${run.outputs.question}",
        "groundtruth": "${run.outputs.answer}",
    }

    side_input_rows = [
        {"line_number": 0, "answer": "I'm fine, thank you.", "question": "How are you?"},
        {"line_number": 1, "answer": "The weather is good.", "question": "How is the weather?"},
    ]

    row = Row.from_dict({}, row_number=0)

    with save_jsonl(side_input_rows) as side_input_dir, TemporaryDirectory() as input_dir:
        input_mapping = InputMapping(Path(input_dir), Path(side_input_dir), mapping)
        mapped = input_mapping.apply(row)

        assert mapped == {"question": "How are you?", "groundtruth": "I'm fine, thank you."}
