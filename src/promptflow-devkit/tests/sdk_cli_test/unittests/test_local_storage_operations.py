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
