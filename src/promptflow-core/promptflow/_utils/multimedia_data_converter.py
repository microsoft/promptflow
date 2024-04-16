import re
from dataclasses import dataclass
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Any, Callable

from promptflow._constants import MessageFormatType
from promptflow._utils._errors import InvalidMessageFormatType
from promptflow._utils.multimedia_utils import BasicMultimediaProcessor, ImageProcessor, OpenaiVisionMultimediaProcessor
from promptflow.contracts.flow import Flow


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
    One multimedia data example from basic message format type: {"data:image/jpg;path": "logo.jpg"}
    """

    # Check if the original_data is a multimedia format according to the current contract version.
    def is_valid_format(self, original_data: Any):
        raise NotImplementedError()

    def extract_info(self, original_data: Any) -> MultimediaInfo:
        """
        Get the MultimediaInfo from the original data. Will include mime_type, resource_type, and content.
        Below is an example for basic message format type:
        {"data:image/jpg;path": "logo.jpg"} -> "image/jpg", "path", "logo.jpg"
        """
        raise NotImplementedError()

    def create_data(self, info: MultimediaInfo) -> Any:
        """
        Create multimedia data from info. Below is an example for basic message format type:
        "image/jpg", "path", "logo.jpg" -> {"data:image/jpg;path": "logo.jpg"}
        """
        raise NotImplementedError()


class BasicMultimediaFormatAdapter(AbstractMultimediaFormatAdapter):
    """
    Basic is our first multimedia contract's message format type,
    supports text and images (path/url/base64).
    Users can specify this version in the yaml file by configuring "message_format: basic".
    If the user does not specify message_format, we will also use the default value "basic".
    Path format example: {"data:image/jpg;path": "logo.jpg"}
    Url format example: {"data:image/jpg;url": "https://example.com/logo.jpg"}
    Base64 format example: {"data:image/jpg;base64": "base64 string"}
    """

    MIME_PATTERN = re.compile(r"^data:(.*);(path|base64|url)$")

    def is_valid_format(self, original_data: Any):
        return isinstance(original_data, dict) and BasicMultimediaProcessor.is_multimedia_dict(original_data)

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


class OpenaiVisionMultimediaFormatAdapter(AbstractMultimediaFormatAdapter):
    """
    OpenaiVision is Image only openai-adapted multimedia contract's message format type,
    supports text and images (path/url/base64).
    Users can specify this version in the yaml file by configuring "message_format: openai-vision"
    Path format example: {"type": "image_file", "image_file": {"path": "logo.jpg"}}
    Url format example: {"type": "image_url", "image_url": {"url": "https://example.com/logo.jpg"}}
    Base64 format example: {"type": "image_url", "image_url": {"url": "data:image/jpg;base64, some_b64_string"}}
    """

    def is_valid_format(self, original_data: Any):
        return isinstance(original_data, dict) and OpenaiVisionMultimediaProcessor.is_multimedia_dict(original_data)

    def extract_info(self, original_data: Any) -> MultimediaInfo:
        if not self.is_valid_format(original_data):
            return None

        image_type = original_data["type"]
        if image_type == "image_file":
            # openai-vision image_dict does not contain mime_type, just use the default value "image/*" here.
            # If we need to use mime_type in the MultimediaConverter in the future,
            # we can convert image_dict to image object and then obtain mime_type from it. Not necessary now.
            return MultimediaInfo("image/*", ResourceType.PATH, original_data["image_file"]["path"])
        if image_type == "image_url":
            image_url = original_data["image_url"]["url"]
            if ImageProcessor.is_base64(image_url):
                return MultimediaInfo("image/*", ResourceType.BASE64, image_url)
            if ImageProcessor.is_url(image_url):
                return MultimediaInfo("image/*", ResourceType.URL, image_url)
        return None

    def create_data(self, info: MultimediaInfo):
        if info.resource_type == ResourceType.PATH:
            return {"type": "image_file", "image_file": {"path": info.content}}
        else:
            return {"type": "image_url", "image_url": {"url": info.content}}


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
        # TODO: read flow.MessageFormatType from flow yaml file.
        # Implement the format_adapter class for the openai-vision type.
        # Then initialize the format_adapter for different MessageFormatType.
        message_format_type = Flow.load_message_format_from_yaml(flow_file)
        if not message_format_type or message_format_type.lower() == MessageFormatType.BASIC:
            self.format_adapter = BasicMultimediaFormatAdapter()
        elif message_format_type.lower() == MessageFormatType.OPENAI_VISION:
            self.format_adapter = OpenaiVisionMultimediaFormatAdapter()
        else:
            raise InvalidMessageFormatType(
                message_format=(
                    f"Invalid message format '{message_format_type}'. "
                    "Supported message formats are ['basic', 'openai-vision']."
                ),
            )

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
