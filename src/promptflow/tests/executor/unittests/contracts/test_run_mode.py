import pytest
from promptflow.contracts.run_mode import RunMode


@pytest.mark.unittest
def test_parse():
    assert RunMode.parse("Test") == RunMode.Test
    assert RunMode.parse("SingleNode") == RunMode.SingleNode
    assert RunMode.parse("Batch") == RunMode.Batch
    assert RunMode.parse("Default") == RunMode.Test

    with pytest.raises(ValueError):
        RunMode.parse(123)
