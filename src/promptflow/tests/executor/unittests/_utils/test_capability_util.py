import pytest

from promptflow._utils.capability_util import get_capability_list


@pytest.mark.unittest
def test_get_capability_list():
    capability_list = get_capability_list()
    assert isinstance(capability_list, list)
    for capability in capability_list:
        assert isinstance(capability, dict)
        assert "name" in capability
        assert "description" in capability
        assert "components" in capability
        assert "state" in capability
