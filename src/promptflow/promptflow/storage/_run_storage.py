# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path
from typing import Union

from promptflow._utils.multimedia_utils import MultimediaProcessor
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_info import RunInfo as NodeRunInfo


class AbstractRunStorage:
    def persist_node_run(self, run_info: NodeRunInfo):
        """Write the node run info to somewhere immediately after the node is executed.

        :param run_info: The run info of the node.
        :type run_info: ~promptflow.contracts.run_info.RunInfo
        """
        raise NotImplementedError("AbstractRunStorage is an abstract class, no implementation for persist_node_run.")

    def persist_flow_run(self, run_info: FlowRunInfo):
        """Write the flow run info to somewhere immediately after one line data is executed for the flow.

        :param run_info: The run info of the node.
        :type run_info: ~promptflow.contracts.run_info.RunInfo
        """
        raise NotImplementedError("AbstractRunStorage is an abstract class, no implementation for persist_flow_run.")


class AbstractBatchRunStorage(AbstractRunStorage):
    def load_node_run_info_for_line(self, line_number: int):
        raise NotImplementedError(
            "AbstractBatchRunStorage is an abstract class, no implementation for load_node_run_info_for_line."
        )

    def load_flow_run_info(self, line_number: int):
        raise NotImplementedError(
            "AbstractBatchRunStorage is an abstract class, no implementation for load_flow_run_info."
        )


class DummyRunStorage(AbstractRunStorage):
    def persist_node_run(self, run_info: NodeRunInfo):
        """Dummy implementation for persist_node_run

        :param run_info: The run info of the node.
        :type run_info: ~promptflow.contracts.run_info.RunInfo
        """
        pass

    def persist_flow_run(self, run_info: FlowRunInfo):
        """Dummy implementation for persist_flow_run

        :param run_info: The run info of the node.
        :type run_info: ~promptflow.contracts.run_info.RunInfo
        """
        pass


class DefaultRunStorage(AbstractRunStorage):
    def __init__(self, base_dir: Path = None, sub_dir: Path = None):
        """Initialize the default run storage.

        :param base_dir: The base directory to store the multimedia data.
        :type base_dir: Path
        :param sub_dir: The sub directory to store the multimedia data.
        :type sub_dir: Path
        """
        self._base_dir = base_dir
        self._sub_dir = sub_dir

    def persist_run_info(self, run_info: Union[FlowRunInfo, NodeRunInfo]):
        """Persist the multimedia data in run info after execution.

        :param run_info: The run info of the node or flow.
        :type run_info: ~promptflow.contracts.run_info.RunInfo or ~promptflow.contracts.run_info.FlowRunInfo
        """
        multimedia_processor = MultimediaProcessor.create(run_info.message_format)
        # Persist and convert images in inputs to path dictionaries.
        # This replaces any image objects with their corresponding file path dictionaries.
        if run_info.inputs:
            run_info.inputs = self._persist_and_convert_images_to_path_dicts(multimedia_processor, run_info.inputs)

        # Persist and convert images in output to path dictionaries.
        # This replaces any image objects with their corresponding file path dictionaries.
        if run_info.output:
            serialized_output = self._persist_and_convert_images_to_path_dicts(multimedia_processor, run_info.output)
            run_info.output = serialized_output
            run_info.result = serialized_output

        # Persist and convert images in api_calls to path dictionaries.
        # The `inplace=True` parameter is used here to ensure that the original list structure holding generator outputs
        # is maintained. This allows us to keep tracking the list as it dynamically changes when the generator is
        # consumed. It is crucial to process the api_calls list in place to avoid losing the reference to the list that
        # holds the generator items, which is essential for tracing generator execution.
        if run_info.api_calls:
            run_info.api_calls = self._persist_and_convert_images_to_path_dicts(
                multimedia_processor, run_info.api_calls, inplace=True
            )

    def persist_node_run(self, run_info: NodeRunInfo):
        """Persist the multimedia data in node run info after the node is executed.
        This method now delegates to the shared persist_run_info method.

        :param run_info: The run info of the node.
        :type run_info: NodeRunInfo
        """
        self.persist_run_info(run_info)

    def persist_flow_run(self, run_info: FlowRunInfo):
        """Persist the multimedia data in flow run info after one line data is executed for the flow.
        This method now delegates to the shared persist_run_info method.

        :param run_info: The run info of the flow.
        :type run_info: FlowRunInfo
        """
        self.persist_run_info(run_info)

    def _persist_and_convert_images_to_path_dicts(
        self, multimedia_processor: MultimediaProcessor, value, inplace=False
    ):
        """Persist image objects within a Python object to disk and convert them to path dictionaries.

        This function recursively processes a given Python object, which can be a list, a dictionary, or a nested
        combination of these, searching for image objects. Each image object encountered is serialized and saved to
        disk in a pre-defined location using the `_base_dir` and `_sub_dir` attributes. The image object within the
        original data structure is then replaced with a dictionary that indicates the file path of the serialized
        image, following the format: `{'data:image/<ext>;path': '.promptflow/intermediate/<image_uuid>.<ext>'}`.

        The operation can be performed in-place on the original object or on a new copy, depending on the value of
        the `inplace` parameter. When `inplace` is set to `True`, the original object is modified; when set to `False`,
        a new object with the converted path dictionaries is returned.

        :param value: The Python object to be processed, potentially containing image objects.
        :type value: Any
        :param inplace: Whether to modify the original object in place (True) or to create a new object with converted
                        path dictionaries (False).
        :type inplace: bool
        :return: The original object with converted path dictionaries if `inplace` is True, otherwise a new object with
                 the conversions.
        :rtype: Any
        """
        return multimedia_processor.persist_multimedia_data(
            value, base_dir=self._base_dir, sub_dir=self._sub_dir, inplace=inplace
        )
