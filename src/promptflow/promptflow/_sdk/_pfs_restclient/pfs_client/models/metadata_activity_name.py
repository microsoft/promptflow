from enum import Enum


class MetadataActivityName(str, Enum):
    PF_FLOW_GENERATE_TOOLS_META = "pf.flow._generate_tools_meta"
    PF_FLOW_NODE_TEST = "pf.flow.node_test"
    PF_FLOW_TEST = "pf.flow.test"

    def __str__(self) -> str:
        return str(self.value)
