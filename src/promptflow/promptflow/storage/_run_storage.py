# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from functools import partial
from pathlib import Path

from promptflow._utils.multimedia_utils import _process_recursively, get_file_reference_encoder
from promptflow.contracts.multimedia import Image
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

    def persist_node_run(self, run_info: NodeRunInfo):
        """Persist the multimedia data in node run info after the node is executed.

        :param run_info: The run info of the node.
        :type run_info: ~promptflow.contracts.run_info.RunInfo
        """
        if run_info.inputs:
            run_info.inputs = self._persist_and_convert_images_to_path_dicts(run_info.inputs)
        if run_info.output:
            serialized_output = self._persist_and_convert_images_to_path_dicts(run_info.output)
            run_info.output = serialized_output
            run_info.result = serialized_output
        if run_info.api_calls:
            run_info.api_calls = self._persist_and_convert_images_to_path_dicts(run_info.api_calls, inplace=True)

    def persist_flow_run(self, run_info: FlowRunInfo):
        """Persist the multimedia data in flow run info after one line data is executed for the flow.

        :param run_info: The run info of the flow.
        :type run_info: ~promptflow.contracts.run_info.FlowRunInfo
        """
        if run_info.inputs:
            run_info.inputs = self._persist_and_convert_images_to_path_dicts(run_info.inputs)
        if run_info.output:
            serialized_output = self._persist_and_convert_images_to_path_dicts(run_info.output)
            run_info.output = serialized_output
            run_info.result = serialized_output
        if run_info.api_calls:
            run_info.api_calls = self._persist_and_convert_images_to_path_dicts(run_info.api_calls, inplace=True)

    def _persist_and_convert_images_to_path_dicts(self, value, inplace=False):
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
        if self._base_dir:
            pfbytes_file_reference_encoder = get_file_reference_encoder(
                folder_path=self._base_dir,
                relative_path=self._sub_dir,
            )
        else:
            pfbytes_file_reference_encoder = None
        serialization_funcs = {Image: partial(Image.serialize, **{"encoder": pfbytes_file_reference_encoder})}
        return _process_recursively(value, process_funcs=serialization_funcs, inplace=inplace)
