# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


class SpanWrapper:
    """
    A wrapper class for spans.
    """

    def __init__(self, wrapped: object):
        """
        Initialize the SpanWrapper with the object to be wrapped.

        :param wrapped: The object to be wrapped.
        """
        object.__setattr__(self, "__wrapped__", wrapped)
        self._self_should_end = True

    def __getattr__(self, name: str) -> object:
        """
        Get attribute from the wrapped object.

        :param name: The name of the attribute.
        :return: The attribute of the wrapped object.
        """
        if name == "__wrapped__":
            raise ValueError(
                "SpanWrapper has not been initialised. "
                "Please ensure that the object to be wrapped is provided during initialization."
            )

        return getattr(self.__wrapped__, name)

    @property
    def __class__(self) -> type:
        """
        Get the class of the wrapped object.

        :return: The class of the wrapped object.
        """
        return self.__wrapped__.__class__

    @__class__.setter
    def __class__(self, value: type):
        """
        Set the class of the wrapped object.

        :param value: The new class of the wrapped object.
        """
        self.__wrapped__.__class__ = value

    @property
    def should_end(self) -> bool:
        """
        Get the should_end property of the SpanWrapper.

        :return: The should_end property of the SpanWrapper.
        """
        return self._self_should_end

    @should_end.setter
    def should_end(self, value: bool):
        """
        Set the should_end property of the SpanWrapper.

        :param value: The new value of the should_end property.
        """
        if not isinstance(value, bool):
            raise ValueError("should_end must be a boolean")
        self._self_should_end = value
