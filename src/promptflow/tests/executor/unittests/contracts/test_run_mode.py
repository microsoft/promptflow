import pytest

from promptflow.contracts.run_mode import RunMode


@pytest.mark.unittest
@pytest.mark.parametrize(
    "run_mode, expected",
    [
        ("Test", RunMode.Test),
        ("SingleNode", RunMode.SingleNode),
        ("Batch", RunMode.Batch),
        ("Default", RunMode.Test),
    ],
)
def test_parse(run_mode, expected):
    assert RunMode.parse(run_mode) == expected


@pytest.mark.unittest
def test_parse_invalid():
    with pytest.raises(ValueError):
        RunMode.parse(123)
