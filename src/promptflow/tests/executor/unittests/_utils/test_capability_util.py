import pytest

from promptflow._utils.capability_util import Capability, CapabilityComponent, CapabilityState, get_capability_list


@pytest.mark.unittest
class TestCapabilityUtil:
    def test_get_capability_list(self):
        capability_list = get_capability_list()
        assert isinstance(capability_list, list)
        assert all(isinstance(capability, Capability) for capability in capability_list)

    def test_capability(self):
        capability = Capability(
            name="ActivateConfig",
            description="Bypass node execution when the node does not meet activate condition.",
            component=CapabilityComponent.EXECUTOR,
            state=CapabilityState.READY,
        )
        capability_dict = capability.to_dict()
        assert isinstance(capability_dict, dict)
        assert "name" in capability_dict
        assert "description" in capability_dict
        assert "component" in capability_dict
        assert "state" in capability_dict
