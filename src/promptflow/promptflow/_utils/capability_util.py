from dataclasses import dataclass
from enum import Enum
from typing import List


class CapabilityState(Enum):
    """The enum of capability state.

    READY: The feature is ready to use.
    E2ETEST: The feature is not ready to be shipped to customer and is in e2e testing.
    """

    READY = "Ready"
    E2ETEST = "E2ETest"


class CapabilityComponent(Enum):
    """The enum of capability component."""

    EXECUTOR = "executor"


@dataclass
class Capability:
    """The dataclass of capability."""

    name: str
    description: str
    components: List[CapabilityComponent]
    state: CapabilityState

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "components": [component.value for component in self.components],
            "state": self.state.value,
        }


CAPABILITY_LIST = [
    Capability(
        name="ActivateConfig",
        description="Bypass node execution when the node does not meet activate condition.",
        components=[CapabilityComponent.EXECUTOR],
        state=CapabilityState.READY,
    ),
]


def get_capability_list():
    capability_list = [capability.to_dict() for capability in CAPABILITY_LIST]
    return capability_list
