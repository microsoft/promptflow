# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from promptflow._sdk.entities._experiment import CommandNode


def command(
    command: str,
    inputs: dict = None,
    outputs: dict = None,
    environment_variables: dict = None,
    code: str = None,
    display_name: str = None,
    **kwargs,
) -> CommandNode:
    """Build a command node in dsl experiment.

    :param command: The command to run.
    :type command: str
    :param inputs: The inputs of the command node.
    :type inputs: dict
    :param outputs: The outputs of the command node.
    :type outputs: dict
    :param environment_variables: The environment variables of the command node.
    :type environment_variables: dict
    :param code: Optional, the code directory of the command node.
    :type code: str
    :param display_name: Optional, the display name of the command node, default to name.
    :type display_name: str
    :return: The command node.
    :rtype: ~promptflow._sdk.entities._experiment.CommandNode
    """
    return CommandNode(
        command=command,
        name=None,  # Name will be set later with var name
        inputs=inputs,
        outputs=outputs,
        environment_variables=environment_variables,
        code=code,
        display_name=display_name,
        **kwargs,
    )
