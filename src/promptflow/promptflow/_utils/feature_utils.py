from dataclasses import dataclass
from enum import Enum


class FeatureState(Enum):
    """The enum of feature state.

    READY: The feature is ready to use.
    E2ETEST: The feature is not ready to be shipped to customer and is in e2e testing.
    """

    READY = "Ready"
    E2ETEST = "E2ETest"


class FeatureComponent(Enum):
    """The enum of feature component."""

    EXECUTOR = "executor"


@dataclass
class Feature:
    """The dataclass of feature."""

    name: str
    description: str
    component: FeatureComponent
    state: FeatureState


def get_feature_list():
    feature_list = [
        Feature(
            name="ActivateConfig",
            description="Bypass node execution when the node does not meet activate condition.",
            component=FeatureComponent.EXECUTOR,
            state=FeatureState.READY,
        ),
    ]

    return feature_list
