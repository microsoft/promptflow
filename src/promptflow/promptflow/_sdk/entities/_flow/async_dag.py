from os import PathLike
from typing import Union

from promptflow._constants import DEFAULT_ENCODING, FlowLanguage
from promptflow._utils.docs import AsyncFlowDoc
from promptflow._utils.yaml_utils import load_yaml_string
from promptflow.exceptions import UserErrorException

from .dag import Flow


class AsyncFlow(Flow):
    __doc__ = AsyncFlowDoc.__doc__

    async def invoke_async(self, inputs: dict) -> "LineResult":
        """Invoke a flow and get a LineResult object."""
        from promptflow._sdk._submitter import TestSubmitter

        if self.language == FlowLanguage.CSharp:
            # Sync C# calling
            # TODO: Async C# support: Task(3002242)
            with TestSubmitter(flow=self, flow_context=self.context).init(
                stream_output=self.context.streaming
            ) as submitter:
                result = submitter.flow_test(inputs=inputs, allow_generator_output=self.context.streaming)
                return result
        else:
            return await super().invoke_async(inputs=inputs)

    # region overrides
    @classmethod
    def load(
        cls,
        source: Union[str, PathLike],
        raise_error=True,
        **kwargs,
    ) -> "AsyncFlow":
        """
        Direct load flow from YAML file.

        :param source: The local yaml source of a flow. Must be a path to a local file.
            If the source is a path, it will be open and read.
            An exception is raised if the file does not exist.
        :type source: Union[PathLike, str]
        :param raise_error: Argument for non-dag flow raise validation error on unknown fields.
        :type raise_error: bool
        :return: An AsyncFlow object
        :rtype: AsyncFlow
        """
        _, flow_path = cls._load_prepare(source)
        with open(flow_path, "r", encoding=DEFAULT_ENCODING) as f:
            flow_content = f.read()
            data = load_yaml_string(flow_content)
            content_hash = hash(flow_content)
        return cls._load(path=flow_path, dag=data, content_hash=content_hash, **kwargs)

    # endregion

    async def __call__(self, *args, **kwargs):
        """Calling flow as a function in async, the inputs should be provided with key word arguments.
        Returns the output of the flow.
        The function call throws UserErrorException: if the flow is not valid or the inputs are not valid.
        SystemErrorException: if the flow execution failed due to unexpected executor error.

        :param args: positional arguments are not supported.
        :param kwargs: flow inputs with key word arguments.
        :return:
        """
        if args:
            raise UserErrorException("Flow can only be called with keyword arguments.")

        result = await self.invoke_async(inputs=kwargs)
        return result.output
