from dataclasses import dataclass
from enum import Enum


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
    component: CapabilityComponent
    state: CapabilityState

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "component": self.component.value,
            "state": self.state.value,
        }


def get_capability_list():
    capability_list = [
        Capability(
            name="ActivateConfig",
            description="Bypass node execution when the node does not meet activate condition.",
            component=CapabilityComponent.EXECUTOR,
            state=CapabilityState.READY,
        ),
    ]

    return capability_list
