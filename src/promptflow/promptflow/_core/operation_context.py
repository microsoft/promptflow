# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import copy
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
    _OTEL_ATTRIBUTES = "_otel_attributes"
    _current_context = ContextVar(_CONTEXT_KEY, default=None)
    USER_AGENT_KEY = "user_agent"
    _DEFAULT_TRACKING_KEYS = {"run_mode", "root_run_id", "flow_id", "batch_input_source"}
    _TRACKING_KEYS = "_tracking_keys"

    def _add_otel_attributes(self, key, value):
        attributes = self.get(OperationContext._OTEL_ATTRIBUTES, {})
        attributes[key] = value
        self[OperationContext._OTEL_ATTRIBUTES] = attributes

    def _remove_otel_attributes(self, keys: list):
        if isinstance(keys, str):
            keys = [keys]
        attributes = self.get(OperationContext._OTEL_ATTRIBUTES, {})
        for key in keys:
            attributes.pop(key, None)
        self[OperationContext._OTEL_ATTRIBUTES] = attributes

    def _get_otel_attributes(self):
        return self.get(OperationContext._OTEL_ATTRIBUTES, {})

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
        if cls._TRACKING_KEYS not in instance:
            instance[cls._TRACKING_KEYS] = copy.copy(cls._DEFAULT_TRACKING_KEYS)
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
            if OperationContext.USER_AGENT_KEY in self:
                yield self.get(OperationContext.USER_AGENT_KEY)
            yield f"promptflow/{VERSION}"

        # strip to avoid leading or trailing spaces, which may cause error when sending request
        ua = " ".join(parts()).strip()
        return ua

    def append_user_agent(self, user_agent: str):
        """Append the user agent string.

        This method appends user agent information to the user_agent attribute of the OperationContext instance.
        If there is no user_agent attribute, it creates one with the given user agent information.

        Args:
            user_agent (str): The user agent information to append.
        """
        if OperationContext.USER_AGENT_KEY in self:
            if user_agent not in self.user_agent:
                self.user_agent = f"{self.user_agent.strip()} {user_agent.strip()}"
        else:
            self.user_agent = user_agent

    def set_batch_input_source_from_inputs_mapping(self, inputs_mapping: Mapping[str, str]):
        """Infer the batch input source from the input mapping and set it in the OperationContext instance.

        This method analyzes the `inputs_mapping` to ascertain the origin of the inputs for a batch operation.
        The `inputs_mapping` should be a dictionary with keys representing input names and values specifying the sources
        of these inputs. Inputs can originate from direct data or from the outputs of a previous run.

        The `inputs_mapping` is dictated entirely by the external caller. For more details on column mapping, refer to
        https://aka.ms/pf/column-mapping. The mapping can include references to both the inputs and outputs of previous
        runs, using a reserved source name 'run' to indicate such references. However, this method specifically checks
        for references to outputs of previous runs, which are denoted by values starting with "${run.outputs". When such
        a reference is found, the `batch_input_source` attribute of the OperationContext instance is set to "Run" to
        reflect that the batch operation is utilizing outputs from a prior run.

        If no values in the `inputs_mapping` start with "${run.outputs", it is inferred that the inputs do not derive
        from a previous run, and the `batch_input_source` is set to "Data".

        Examples of `inputs_mapping`:
            - Referencing a previous run's output:
                {'input1': '${run.outputs.some_output}', 'input2': 'direct_data'}
              In this case, 'input1' is sourced from a prior run's output, and 'input2' is from direct data.
              The `batch_input_source` would be set to "Run".

            - Sourcing directly from data:
                {'input1': 'data_source1', 'input2': 'data_source2'}
              Since no values start with "${run.outputs", the `batch_input_source` is set to "Data".

        Args:
            inputs_mapping (Mapping[str, str]): A dictionary mapping input names to their sources, where the sources
            can be either direct data or outputs from a previous run. The structure and content of this mapping are
            entirely under the control of the external caller.

        Returns:
            None
        """
        if inputs_mapping and any(
            isinstance(value, str) and value.startswith("${run.outputs") for value in inputs_mapping.values()
        ):
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

    def _get_tracking_info(self):
        keys = getattr(self, self._TRACKING_KEYS, self._DEFAULT_TRACKING_KEYS)
        return {k: v for k, v in self.items() if k in keys}
