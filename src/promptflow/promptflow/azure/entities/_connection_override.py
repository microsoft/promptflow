# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

class ConnectionOverride:
    """
    :connection_source_type: Possible values include: "Node", "NodeInput".
    :node_name: Node name
    :node_input_name: Node input name
    :connection_name: Connection name
    :deployment_name: Deployment name
    """
    def __init__(self, node_name=None, node_input_name=None, connection_name=None, deployment_name=None):
        if node_input_name:
            self.connection_name = "NodeInput"
        elif node_name:
            self.connection_name = "Node"
        else:
            raise ValueError("Either node_name or node_input_name must be provided.")
        self.node_name = node_name
        self.node_input_name = node_input_name
        self.connection_name = connection_name
        self.deployment_name = deployment_name
