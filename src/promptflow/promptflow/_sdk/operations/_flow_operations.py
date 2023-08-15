# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from os import PathLike
from typing import List, Union

from promptflow._sdk._constants import CHAT_HISTORY
from promptflow._sdk.operations._test_submitter import TestSubmitter
from promptflow.exceptions import UserErrorException


class FlowOperations:
    """FlowOperations."""

    def __init__(self):
        pass

    def test(
        self,
        flow: Union[str, PathLike],
        *,
        inputs: dict = None,
        variant: str = None,
        node: str = None,
        environment_variables: dict = None,
    ):
        """Test flow or node locally

        :param flow: path to flow directory to test
        :param inputs: Input data for the flow test
        :param variant: Node & variant name in format of ${node_name.variant_name}, will use default variant
           if not specified.
        :param node: If specified it will only test this node, else it will test the flow.
        :param environment_variables: Environment variables to set by specifying a property path and value.
           Example: {"key1": "${my_connection.api_key}", "key2"="value2"}
           The value reference to connection keys will be resolved to the actual value,
           and all environment variables specified will be set into os.environ.
        :return: The result of flow or node
        """
        result = self._test(
            flow=flow,
            inputs=inputs,
            variant=variant,
            node=node,
            environment_variables=environment_variables,
        )
        TestSubmitter._raise_error_when_test_failed(result, show_trace=node is not None)
        return result.output

    def _test(
        self,
        flow: Union[str, PathLike],
        *,
        inputs: dict = None,
        variant: str = None,
        node: str = None,
        environment_variables: dict = None,
    ):
        """Test flow or node locally

        :param flow: path to flow directory to test
        :param inputs: Input data for the flow test
        :param variant: Node & variant name in format of ${node_name.variant_name}, will use default variant
           if not specified.
        :param node: If specified it will only test this node, else it will test the flow.
        :param environment_variables: Environment variables to set by specifying a property path and value.
           Example: {"key1": "${my_connection.api_key}", "key2"="value2"}
           The value reference to connection keys will be resolved to the actual value,
           and all environment variables specified will be set into os.environ.
        :return: Executor result
        """
        from promptflow._sdk._load_functions import load_flow

        flow = load_flow(flow)
        with TestSubmitter(flow=flow, variant=variant).init() as submitter:
            flow_inputs, dependency_nodes_outputs = submitter._resolve_data(
                node_name=node, inputs=inputs
            )
            if self._is_chat_flow(submitter.dataplane_flow) and flow_inputs.get(
                CHAT_HISTORY, None
            ):
                flow_inputs[CHAT_HISTORY] = []
            if node:
                return submitter.node_test(
                    node_name=node,
                    flow_inputs=flow_inputs,
                    dependency_nodes_outputs=dependency_nodes_outputs,
                    environment_variables=environment_variables,
                    stream=True,
                )
            else:
                return submitter.flow_test(
                    inputs=flow_inputs,
                    environment_variables=environment_variables,
                    stream=True,
                )

    @staticmethod
    def _is_chat_flow(flow):
        """
        Check if the flow is chat flow.
        Check if chat_history in the flow input and only on chat input to determine if it is a chat flow.
        """
        chat_inputs = [item for item in flow.inputs.values() if item.is_chat_input]
        return len(chat_inputs) == 1 and CHAT_HISTORY in flow.inputs

    def _chat(
        self,
        flow,
        *,
        inputs: dict = None,
        variant: str = None,
        environment_variables: dict = None,
        **kwargs,
    ) -> List:
        """Interact with Chat Flow. Only chat flow supported.

        :param flow: path to flow directory to chat
        :param inputs: Input data for the flow to chat
        :param environment_variables: Environment variables to set by specifying a property path and value.
           Example: {"key1": "${my_connection.api_key}", "key2"="value2"}
           The value reference to connection keys will be resolved to the actual value,
           and all environment variables specified will be set into os.environ.
        """
        from promptflow._sdk._load_functions import load_flow

        flow = load_flow(flow)
        with TestSubmitter(flow=flow, variant=variant).init() as submitter:
            is_chat_flow = self._is_chat_flow(submitter.dataplane_flow)
            if not is_chat_flow:
                raise UserErrorException("Only support chat flow in interactive mode.")

            info_msg = f"Welcome to chat flow, {submitter.dataplane_flow.name}."
            print("=" * len(info_msg))
            print(info_msg)
            print("Press Enter to send your message.")
            print("You can quit with ctrl+Z.")
            print("=" * len(info_msg))
            submitter._chat_flow(
                inputs=inputs,
                environment_variables=environment_variables,
                show_step_output=kwargs.get("show_step_output", False),
            )
