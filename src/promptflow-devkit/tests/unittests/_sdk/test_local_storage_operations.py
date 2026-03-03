"""Unit tests for the fillna dtype fix in _local_storage_operations.py.

Issue #2702: outputs.fillna(value="(Failed)", inplace=True) raises
FutureWarning (and will eventually raise ValueError) in pandas 2.x when the
DataFrame contains float64 columns and the fill value is a string.

Fix: cast to object dtype first and use .where(notna()) so no silent
downcasting warning is triggered.

These tests are written as pure pandas tests so they have no dependency
on the broader promptflow import tree.
"""
import warnings

import pandas as pd
import pytest

LINE_NUMBER = "line_number"


# ---------------------------------------------------------------------------
# Helpers mirroring the logic from _local_storage_operations.py
# ---------------------------------------------------------------------------

def _outputs_padding(df: pd.DataFrame, inputs_line_numbers) -> pd.DataFrame:
    """Mirror of RunStorage._outputs_padding (static method)."""
    if len(df) == len(inputs_line_numbers):
        return df
    missing_lines = []
    lines_set = set(df[LINE_NUMBER].values)
    for i in inputs_line_numbers:
        if i not in lines_set:
            missing_lines.append({LINE_NUMBER: i})
    df_to_append = pd.DataFrame(missing_lines)
    res = pd.concat([df, df_to_append], ignore_index=True)
    res = res.sort_values(by=LINE_NUMBER, ascending=True)
    return res


class TestOutputsPadding:
    """Tests for the _outputs_padding logic."""

    def test_no_padding_needed_when_lengths_match(self):
        df = pd.DataFrame({LINE_NUMBER: [0, 1, 2], "output": ["a", "b", "c"]})
        result = _outputs_padding(df, [0, 1, 2])
        assert len(result) == 3

    def test_missing_lines_get_nan_rows(self):
        # Line 1 is missing from outputs (that run failed)
        df = pd.DataFrame({LINE_NUMBER: [0, 2], "score": [0.9, 0.7]})
        result = _outputs_padding(df, [0, 1, 2])
        assert len(result) == 3
        row = result[result[LINE_NUMBER] == 1]
        assert row["score"].isna().all()

    def test_sorted_by_line_number_after_padding(self):
        df = pd.DataFrame({LINE_NUMBER: [2, 0], "val": [10, 20]})
        result = _outputs_padding(df, [0, 1, 2])
        assert list(result[LINE_NUMBER]) == [0, 1, 2]


class TestFillnaNoFutureWarning:
    """Regression tests for issue #2702.

    pandas 2.x raises FutureWarning when filling NaN in a float64 column
    with a string value (or when downcasting after astype/fillna).

    Fix: use .astype(object).where(outputs.notna(), other="(Failed)")
    which avoids all dtype-coercion warnings.
    """

    def _make_outputs_with_failure(self) -> pd.DataFrame:
        """Simulate what _outputs_padding produces when a run fails.

        The failed line contributes NaN for numeric columns because
        pd.concat introduces NaN for missing values, and float64 is the
        default dtype for columns that started as numeric.
        """
        successful = pd.DataFrame({LINE_NUMBER: [0, 2], "score": [0.9, 0.7]})
        failed_row = pd.DataFrame({LINE_NUMBER: [1]})  # only LINE_NUMBER, no score
        merged = pd.concat([successful, failed_row], ignore_index=True)
        return merged.sort_values(by=LINE_NUMBER, ascending=True).reset_index(drop=True)

    def test_where_with_string_on_float64_column_raises_no_futurewarning(self):
        outputs = self._make_outputs_with_failure()

        # The fixed expression must not raise any FutureWarning
        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            filled = outputs.astype(object).where(outputs.notna(), other="(Failed)")

        failed_idx = filled[filled[LINE_NUMBER] == 1].index[0]
        assert filled.loc[failed_idx, "score"] == "(Failed)"
        good_idx = filled[filled[LINE_NUMBER] == 0].index[0]
        assert filled.loc[good_idx, "score"] == pytest.approx(0.9)

    def test_where_fills_all_nan_cells_with_failed_marker(self):
        outputs = self._make_outputs_with_failure()
        filled = outputs.astype(object).where(outputs.notna(), other="(Failed)")

        # Exactly one row should have been filled (the failed line)
        assert (filled["score"] == "(Failed)").sum() == 1

    def test_where_preserves_existing_values(self):
        outputs = self._make_outputs_with_failure()
        filled = outputs.astype(object).where(outputs.notna(), other="(Failed)")

        successful_scores = filled[filled[LINE_NUMBER] != 1]["score"].tolist()
        assert successful_scores == pytest.approx([0.9, 0.7])

    def test_where_works_with_multiple_numeric_columns(self):
        """Covers DataFrames with several float64 columns (common in real runs)."""
        successful = pd.DataFrame({
            LINE_NUMBER: [0, 2],
            "score": [0.9, 0.7],
            "latency": [1.2, 0.8],
        })
        failed_row = pd.DataFrame({LINE_NUMBER: [1]})
        merged = pd.concat([successful, failed_row], ignore_index=True)
        merged = merged.sort_values(by=LINE_NUMBER, ascending=True)

        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            filled = merged.astype(object).where(merged.notna(), other="(Failed)")

        failed_row_data = filled[filled[LINE_NUMBER] == 1]
        assert failed_row_data["score"].iloc[0] == "(Failed)"
        assert failed_row_data["latency"].iloc[0] == "(Failed)"

    def test_old_inplace_fillna_raises_futurewarning_on_pandas_2(self):
        """Documents that the OLD code pattern emits FutureWarning on pandas 2.x.

        This test is expected to collect a FutureWarning — if it stops doing so
        (e.g. pandas removes the warning), the newer fix is still safe.
        """
        major = int(pd.__version__.split(".")[0])
        if major < 2:
            pytest.skip("FutureWarning only applies to pandas 2.x")

        outputs = self._make_outputs_with_failure()

        with pytest.warns(FutureWarning):
            outputs.fillna(value="(Failed)", inplace=True)
