# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import copy
from contextvars import ContextVar
from typing import Dict

from ._version import VERSION


class OperationContext(Dict):
    """The OperationContext class.

    This class is used to store the context information for the current operation. It is a dictionary-like class
    that can be used to store any primitive context information. The object is a context variable that can be
    accessed from anywhere in the current context. The context information is used to provide additional information
    to the service for logging and telemetry purposes.
    """

    _CONTEXT_KEY = "operation_context"
    _current_context = ContextVar(_CONTEXT_KEY, default=None)
    USER_AGENT_KEY = "user_agent"
    REQUEST_ID_KEY = "request_id"
    EXECUTION_TARGET = "execution_target"
    _DEFAULT_TRACING_KEYS = "_default_tracing_keys"
    _OTEL_ATTRIBUTES = "_otel_attributes"
    _TRACKING_KEYS = "_tracking_keys"

    def copy(self):
        ctx = OperationContext(self)
        ctx[OperationContext._OTEL_ATTRIBUTES] = copy.copy(self._get_otel_attributes())
        return ctx

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
        attr_dict = self.get(OperationContext._OTEL_ATTRIBUTES, {})
        # Filter None value out to avoid error.
        # case: Experiment run may set 'reference.batch_run_id' to None which cause some exception.
        return {k: v for k, v in attr_dict.items() if v is not None}

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
        if cls._TRACKING_KEYS not in instance and cls._DEFAULT_TRACING_KEYS in instance:
            instance[cls._TRACKING_KEYS] = copy.copy(instance[cls._DEFAULT_TRACING_KEYS])
        return instance

    @classmethod
    def set_instance(cls, instance):
        cls._current_context.set(instance)

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
            yield f"promptflow-tracing/{VERSION}"

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
            # TODO: this judgement can be wrong when an user agent is a substring of another,
            #  e.g. "Mozilla/5.0" and "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            #  however, changing this code may impact existing logic, so won't change it now
            if user_agent not in self.user_agent:
                self.user_agent = f"{self.user_agent.strip()} {user_agent.strip()}"
        else:
            self.user_agent = user_agent

    def get_request_id(self):
        if OperationContext.REQUEST_ID_KEY in self:
            return self.get(OperationContext.REQUEST_ID_KEY)
        return "unknown"

    def set_default_tracing_keys(self, keys: set):
        self[self._DEFAULT_TRACING_KEYS] = keys
        if not hasattr(self, self._TRACKING_KEYS):
            self[self._TRACKING_KEYS] = copy.copy(keys)
        else:
            for key in keys:
                if key not in self[self._TRACKING_KEYS]:
                    self[self._TRACKING_KEYS].add(key)

    def set_execution_target(self, execution_target: str):
        # Set in the context for getting tracking info
        # Set in otel attributes for telemetry
        self[OperationContext.EXECUTION_TARGET] = execution_target
        self._add_otel_attributes(OperationContext.EXECUTION_TARGET, execution_target)

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
        keys = getattr(self, self._TRACKING_KEYS, getattr(self, self._DEFAULT_TRACING_KEYS, []))
        return {k: v for k, v in self.items() if k in keys}
