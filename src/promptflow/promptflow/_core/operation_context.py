# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from contextvars import ContextVar
from typing import Dict, Mapping

from promptflow._version import VERSION


class OperationContext(Dict):
    """The OperationContext class.

    This class is used to store the context information for the current operation. It is a dictionary-like class
    that can be used to store any primitive context information. The object is a context variable that can be
    accessed from anywhere in the current context. The context information is used to provide additional information
    to the service for logging and telemetry purposes.
    """

    _CONTEXT_KEY = "operation_context"
    _current_context = ContextVar(_CONTEXT_KEY, default=None)

    @classmethod
    def get_instance(cls):
        """Get the OperationContext instance.

        This method returns the OperationContext instance from the current context.
        If there is no instance in the current context, it creates a new one and sets it in the current context.

        Returns:
            OperationContext: The OperationContext instance.
        """
        # get the OperationContext instance from the current context
        instance = cls._current_context.get()
        if instance is None:
            # create a new instance and set it in the current context
            instance = OperationContext()
            cls._current_context.set(instance)
        return instance

    def __setattr__(self, name, value):
        """Set the attribute.

        This method sets an attribute with the given name and value in the OperationContext instance.
        The name must be a string and the value must be a primitive.

        Args:
            name (str): The name of the attribute.
            value (int, float, str, bool, or None): The value of the attribute.

        Raises:
            TypeError: If name is not a string or value is not a primitive.
        """
        # check that name is a string
        if not isinstance(name, str):
            raise TypeError("Name must be a string")
        # check that value is a primitive
        if value is not None and not isinstance(value, (int, float, str, bool)):
            raise TypeError("Value must be a primitive")
        # set the item in the data attribute
        self[name] = value

    def __getattr__(self, name):
        """Get the attribute.

        This method returns the attribute with the given name from the OperationContext instance.
        If there is no such attribute, it returns the default attribute from the super class.

        Args:
            name (str): The name of the attribute.

        Returns:
            int, float, str, bool, or None: The value of the attribute.
        """
        if name in self:
            return self[name]
        else:
            super().__getattribute__(name)

    def __delattr__(self, name):
        """Delete the attribute.

        This method deletes the attribute with the given name from the OperationContext instance.
        If there is no such attribute, it deletes the default attribute from the super class.

        Args:
            name (str): The name of the attribute.
        """
        if name in self:
            del self[name]
        else:
            super().__delattr__(name)

    def get_user_agent(self):
        """Get the user agent string.

        This method returns the user agent string for the OperationContext instance.
        The user agent string consists of the promptflow-sdk version and any additional user agent information stored in
        the user_agent attribute.

        Returns:
            str: The user agent string.
        """

        def parts():
            if "user_agent" in self:
                yield self.get("user_agent")
            yield f"promptflow/{VERSION}"

        return " ".join(parts())

    def append_user_agent(self, user_agent: str):
        """Append the user agent string.

        This method appends user agent information to the user_agent attribute of the OperationContext instance.
        If there is no user_agent attribute, it creates one with the given user agent information.

        Args:
            user_agent (str): The user agent information to append.
        """
        if "user_agent" in self:
            if user_agent not in self.user_agent:
                self.user_agent = f"{self.user_agent} {user_agent}"
        else:
            self.user_agent = user_agent

    def infer_batch_input_source_from_inputs_mapping(self, inputs_mapping: Mapping[str, str]):
        """Infer the batch input source from the input mapping and set it in the OperationContext instance.

        This method examines the provided `inputs_mapping` to determine the source of the inputs for a batch operation.
        The `inputs_mapping` is a dictionary where keys represent the input names and the values represent the sources
        of these inputs. The source of an input can be direct data or the output of a previous run.

        If any value in the `inputs_mapping` starts with "${run.outputs", it is considered as an input coming from the
        output of a previous run. In this scenario, the `batch_input_source` attribute of the OperationContext instance
        is set to "Run" to indicate that the batch inputs are sourced from a previous run's outputs.

        Conversely, if none of the values start with "${run.outputs", the inputs are considered as not coming from a
        previous run and the `batch_input_source` attribute is set to "Data".

        It is important to note that the `inputs_mapping` is fully controlled by the external caller and can reference
        both inputs and outputs of previous runs. However, only references to run outputs are used to set the
        `batch_input_source` to "Run".

        If the `inputs_mapping` is None or empty, the method does nothing and returns without setting the
        `batch_input_source`.

        Example of `inputs_mapping` where input is sourced from a previous run's output:
            {'input1': '${run.outputs.some_output}', 'input2': 'direct_data'}
        Here, 'input1' is sourced from the output of a previous run, while 'input2' is sourced directly from data.
        The `batch_input_source` would be set to "Run" in this case.

        Example of `inputs_mapping` where input is sourced directly from data:
            {'input1': 'data_source1', 'input2': 'data_source2'}
        Since no values start with "${run.outputs", the `batch_input_source` would be set to "Data".

        Args:
            inputs_mapping (Mapping[str, str]): A mapping from input names to their sources, where the sources
            can be either direct data or the output of a previous run. The mapping is fully controlled by the
            external caller.

        Returns:
            None
        """
        if inputs_mapping is None or not inputs_mapping:
            return
        if any(value.startswith("${run.outputs") for value in inputs_mapping.values()):
            self.batch_input_source = "Run"
        else:
            self.batch_input_source = "Data"

    def get_context_dict(self):
        """Get the context dictionary.

        This method returns the context dictionary for the OperationContext instance.
        The context dictionary is a dictionary that contains all the context information stored in the OperationContext
        instance.

        Returns:
            dict: The context dictionary.
        """
        return dict(self)
