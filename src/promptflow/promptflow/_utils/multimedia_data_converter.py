import re
from dataclasses import dataclass
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Any, Callable

from promptflow._utils.multimedia_utils import is_multimedia_dict


class ResourceType(Enum):
    """
    Enumeration of different types of multimedia resources.
    We support path, URL, and base64 data.
    """

    PATH = "path"
    URL = "url"
    BASE64 = "base64"


@dataclass
class MultimediaInfo:
    """
    Data class that holds information about a multimedia resource.
    """

    mime_type: str  # The MIME type of the multimedia resource.
    resource_type: ResourceType  # The type of the resource as defined in ResourceType.
    content: str  # The content of the multimedia resource (path, URL, or base64 string).


class AbstractMultimediaFormatAdapter:
    """
    Abstract base class for adapting multimedia formats.
    This class provides an interface for extracting multimedia information
    from various data formats or constructing data formats from multimedia information.

    Subclasses should implement methods for specific contract version.

    A MultimediaInfo object contains the mime_type, resource_type, and the actual content
    of the multimedia resource.
    The multimedia data is typically represented as a dictionary
    with keys and values conforming to a specific multimedia data contract.
    One multimedia data example from 20231201 version: {"data:image/jpg;path": "logo.jpg"}
    """

    # Check if the original_data is a multimedia format according to the current contract version.
    def is_valid_format(self, original_data: Any):
        raise NotImplementedError()

    def extract_info(self, original_data: Any) -> MultimediaInfo:
        """
        Get the MultimediaInfo from the original data. Will include mime_type, resource_type, and content.
        Below is an example for the 20231201 version:
        {"data:image/jpg;path": "logo.jpg"} -> "image/jpg", "path", "logo.jpg"
        """
        raise NotImplementedError()

    def create_data(self, info: MultimediaInfo) -> Any:
        """
        Create multimedia data from info. Below is an example for the 20231201 version:
        "image/jpg", "path", "logo.jpg" -> {"data:image/jpg;path": "logo.jpg"}
        """
        raise NotImplementedError()


class MultimediaFormatAdapter20231201(AbstractMultimediaFormatAdapter):
    """
    20231201 version is our first contract's version, supports text and images (path/url/base64).
    20231201 is the version number assigned by the customer in the YAML file.
    Path format example: {"data:image/jpg;path": "logo.jpg"}
    Url format example: {"data:image/jpg;url": "https://example.com/logo.jpg"}
    Base64 format example: {"data:image/jpg;base64": "base64 string"}
    """

    MIME_PATTERN = re.compile(r"^data:(.*);(path|base64|url)$")

    def is_valid_format(self, original_data: Any):
        return isinstance(original_data, dict) and is_multimedia_dict(original_data)

    def extract_info(self, original_data: Any) -> MultimediaInfo:
        if not self.is_valid_format(original_data):
            return None
        for key in original_data:
            match = re.match(self.MIME_PATTERN, key)
            if match:
                mime_type, resource_type = match.group(1), match.group(2)
                content = original_data[key]
                return MultimediaInfo(mime_type, ResourceType(resource_type), content)
        return None

    def create_data(self, info: MultimediaInfo):
        return {f"data:{info.mime_type};{info.resource_type.value}": info.content}


class AbstractMultimediaInfoConverter:
    def convert(self, info: MultimediaInfo) -> MultimediaInfo:
        """
        Change info's mime type/resource type/content based on the client's logic.
        For cases that do not need to be changed, just return the original info.

        :param info: The MultimediaInfo to be converted.
        :type info: MultimediaInfo
        :return: The converted MultimediaInfo.
        :rtype: MultimediaInfo
        """
        raise NotImplementedError()


class MultimediaConverter:
    def __init__(self, flow_file: Path):
        """
        Initialize the MultimediaConverter.

        :param flow_file: The path to the YAML file. The YAML content will be used to determine the contract version.
        :type flow_file: Path
        """
        # TODO: check yaml content to determine the current contract version.
        # Different contract version will have different multimedia format.
        # The version exists in the yaml file, so we need to load the yaml to get version and init converter.
        self.format_adapter = MultimediaFormatAdapter20231201()

    def convert_content_recursively(self, content: Any, client_converter: AbstractMultimediaInfoConverter):
        """
        Recursively converts multimedia data format in content.

        :param content: The object that may contain multimedia data.
        :type content: Any
        :param client_converter: The converter to modify multimedia info based on the client's logic.
        :type client_converter: AbstractMultimediaInfoConverter
        :return: The content with changed multimedia format.
        :rtype: Any
        """
        process_func = partial(self._convert_content, converter=client_converter)
        return self._process_content_recursively(content, process_func=process_func)

    def _convert_content(self, original_data: Any, converter: AbstractMultimediaInfoConverter):
        if not self.format_adapter.is_valid_format(original_data):
            return original_data
        info = self.format_adapter.extract_info(original_data)
        # When can't extract multimedia info from original_data, return original_data directly.
        if info is None:
            return original_data
        info = converter.convert(info)
        return self.format_adapter.create_data(info)

    def _process_content_recursively(self, content: Any, process_func: Callable):
        if isinstance(content, list):
            return [self._process_content_recursively(item, process_func) for item in content]
        elif isinstance(content, dict):
            if self.format_adapter.is_valid_format(content):
                return process_func(original_data=content)
            else:
                return {k: self._process_content_recursively(v, process_func) for k, v in content.items()}
        else:
            return content
