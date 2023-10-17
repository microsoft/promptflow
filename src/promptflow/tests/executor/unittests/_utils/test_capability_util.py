import pytest

from promptflow._utils.capability_util import Capability, get_capability_list


@pytest.mark.unittest
class TestCapabilityUtil:
    def test_get_capability_list(self):
        capability_list = get_capability_list()
        assert isinstance(capability_list, list)
        assert all(isinstance(capability, Capability) for capability in capability_list)
