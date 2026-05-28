# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pandas as pd
import pytest

from promptflow._sdk._constants import LINE_NUMBER
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations


@pytest.mark.unittest
class TestLocalStorageOperations:
    def test_outputs_padding(self) -> None:
        data = [
            {LINE_NUMBER: 1, "col": "a"},
            {LINE_NUMBER: 2, "col": "b"},
        ]
        df = pd.DataFrame(data)

        df_with_padding = LocalStorageOperations._outputs_padding(df, inputs_line_numbers=[0, 1, 2, 3, 4])
        df_with_padding.fillna("", inplace=True)
        assert len(df_with_padding) == 5
        assert df_with_padding.iloc[0].to_dict() == {LINE_NUMBER: 0, "col": ""}
        assert df_with_padding.iloc[1].to_dict() == {LINE_NUMBER: 1, "col": "a"}
        assert df_with_padding.iloc[2].to_dict() == {LINE_NUMBER: 2, "col": "b"}
        assert df_with_padding.iloc[3].to_dict() == {LINE_NUMBER: 3, "col": ""}
        assert df_with_padding.iloc[4].to_dict() == {LINE_NUMBER: 4, "col": ""}

        # in evaluation run, inputs may not have all line number
        df_with_padding = LocalStorageOperations._outputs_padding(df, inputs_line_numbers=[1, 2, 4])
        df_with_padding.fillna("", inplace=True)
        assert len(df_with_padding) == 3
        assert df_with_padding.iloc[0].to_dict() == {LINE_NUMBER: 1, "col": "a"}
        assert df_with_padding.iloc[1].to_dict() == {LINE_NUMBER: 2, "col": "b"}
        assert df_with_padding.iloc[2].to_dict() == {LINE_NUMBER: 4, "col": ""}

    def test_load_inputs_and_outputs_sorts_inputs_by_line_number(
        self, tmp_path
    ) -> None:
        """Inputs returned by load_inputs_and_outputs must be sorted by line_number.

        Regression test for https://github.com/microsoft/promptflow/issues/2646

        When the async executor writes results in a different order than the
        input dataset, the raw inputs JSON file can have rows in a non-sequential
        order (e.g. [2, 0, 1]).  _outputs_padding() already sorts outputs by
        line_number, but inputs were left unsorted.  get_details() merges the
        two DataFrames positionally, so mismatched orderings caused input rows
        to be paired with the wrong output rows.
        """
        import json

        # Write inputs file with rows in out-of-order line_number sequence
        inputs_data = [
            {LINE_NUMBER: 2, "query": "third"},
            {LINE_NUMBER: 0, "query": "first"},
            {LINE_NUMBER: 1, "query": "second"},
        ]
        inputs_path = tmp_path / "inputs.jsonl"
        with open(inputs_path, "w") as f:
            for row in inputs_data:
                f.write(json.dumps(row) + "\n")

        # Write outputs file with rows in sorted line_number sequence
        outputs_data = [
            {LINE_NUMBER: 0, "answer": "ans0"},
            {LINE_NUMBER: 1, "answer": "ans1"},
            {LINE_NUMBER: 2, "answer": "ans2"},
        ]
        outputs_path = tmp_path / "outputs.jsonl"
        with open(outputs_path, "w") as f:
            for row in outputs_data:
                f.write(json.dumps(row) + "\n")

        # Patch the LocalStorageOperations instance to point at our temp files
        # without needing a full Run / directory tree.
        ops = object.__new__(LocalStorageOperations)
        ops._sdk_inputs_path = inputs_path
        ops._sdk_output_path = outputs_path

        inputs, outputs = ops.load_inputs_and_outputs()

        # inputs must be in ascending line_number order after the fix
        assert list(inputs[LINE_NUMBER]) == [0, 1, 2], (
            "load_inputs_and_outputs() returned inputs in wrong order; "
            f"got line_numbers={list(inputs[LINE_NUMBER])}"
        )
        assert list(inputs["query"]) == ["first", "second", "third"], (
            "Input rows are not aligned with their line_numbers after sort"
        )

        # outputs must also be in ascending line_number order (already guaranteed
        # by _outputs_padding / set_index, just verify the contract is intact)
        assert list(outputs.index) == [0, 1, 2]
