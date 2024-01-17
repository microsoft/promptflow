from functools import partial
from pathlib import Path
from typing import Any, Callable

from promptflow._utils.multimedia_utils import _get_multimedia_info, is_multimedia_dict


# Format converter to switch multimedia expression between path and url for each contract version.
class AbstractMultimediaFormatConverter:
    # Check if the original_data is a multimedia format according to current contract version.
    def is_multimedia_format(self, original_data: Any):
        raise NotImplementedError()

    # Get the path from multimedia data. Below is example for 20231201 version:
    # {"data:image/jpg;path": "logo.jpg"} -> "logo.jpg"
    def get_path_from_multimedia_data(self, original_data: Any):
        raise NotImplementedError()

    # Get the url from multimedia data. Below is example for 20231201 version:
    # {"data:image/jpg;url": "https://example.com/logo.jpg"} -> "https://example.com/logo.jpg"
    def get_url_from_multimedia_data(self, original_data: Any):
        raise NotImplementedError()

    # Create multimedia data from path. Below is example for 20231201 version:
    # original_data + "new_logo.jpg" -> {"data:image/jpg;path": "new_logo.jpg"}
    def create_multimedia_data_from_path(self, original_data: Any, path: str):
        raise NotImplementedError()

    # Create multimedia data from url. Below is example for 20231201 version:
    # original_data + "https://example.com/logo.jpg" -> {"data:image/jpg;url": "https://example.com/logo.jpg"}
    def create_multimedia_data_from_url(self, original_data: Any, url: str):
        raise NotImplementedError()


# 20231201 version is our first contract's version, supports text and images (path/url/base64).
# 20231201 is version number customer assign in yaml file.
# Path format example: {"data:image/jpg;path": "logo.jpg"}
# Url format example: {"data:image/jpg;url": "https://example.com/logo.jpg"}
# Base64 format example: {"data:image/jpg;base64": "base64 string"}
class MultimediaFormatConverter20231201(AbstractMultimediaFormatConverter):
    PATH_RESOURCE_TYPE = "path"
    URL_RESOURCE_TYPE = "url"

    def is_multimedia_format(self, original_data: Any):
        return isinstance(original_data, dict) and is_multimedia_dict(original_data)

    def _get_path_or_url_from_multimedia_data(self, original_data: Any, resource_type: str):
        if self.is_multimedia_format(original_data):
            for key in original_data:
                _, resource = _get_multimedia_info(key)
                if resource == resource_type:
                    return original_data[key]
        return None

    def get_path_from_multimedia_data(self, original_data: Any):
        return self._get_path_or_url_from_multimedia_data(original_data, self.PATH_RESOURCE_TYPE)

    def get_url_from_multimedia_data(self, original_data: Any):
        return self._get_path_or_url_from_multimedia_data(original_data, self.URL_RESOURCE_TYPE)

    def _create_multimedia_data_from_path_or_url(self, original_data: Any, value: str, resource_type: str):
        if self.is_multimedia_format(original_data):
            for key in original_data:
                format, _ = _get_multimedia_info(key)
                return {f"data:image/{format};{resource_type}": value}
        return None

    def create_multimedia_data_from_path(self, original_data: Any, path: str):
        return self._create_multimedia_data_from_path_or_url(original_data, path, self.PATH_RESOURCE_TYPE)

    def create_multimedia_data_from_url(self, original_data: Any, url: str):
        return self._create_multimedia_data_from_path_or_url(original_data, url, self.URL_RESOURCE_TYPE)


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
        self.format_converter = MultimediaFormatConverter20231201()

    def convert_url_to_path_recursively(self, content: Any, url_to_path_converter: Callable[[str], str]):
        """
        Recursively convert URLs to paths in content may contains multimedia data.

        :param value: The object may contains multimedia data.
        :type value: Any
        :param convert_url_to_path: The function to convert URLs to paths. May also include file downloading logic.
        :type convert_url_to_path: Callable[[str], str]
        :return: The data with URLs converted to paths.
        :rtype: Any
        """
        process_func = partial(self._convert_url_to_path, converter=url_to_path_converter)
        return self._process_content_recursively(content, process_func=process_func)

    def convert_path_to_url_recursively(self, content: Any, path_to_url_converter: Callable[[str], str]):
        """
        Recursively convert paths to URLs in content may contains multimedia data.

        :param value: The object may contains multimedia data.
        :type value: Any
        :param convert_path_to_url: The function to convert paths to URLs. May also include file uploading logic.
        :type convert_path_to_url: Callable[[str], str]
        :return: The data with paths converted to URLs.
        :rtype: Any
        """
        process_func = partial(self._convert_path_to_url, converter=path_to_url_converter)
        return self._process_content_recursively(content, process_func=process_func)

    def _convert_url_to_path(self, original_data: Any, converter: Callable[[str], str]):
        if self.format_converter.is_multimedia_format(original_data):
            url = self.format_converter.get_url_from_multimedia_data(original_data)
            # If original_data is not a url, return original_data directly.
            if url is None:
                return original_data
            return self.format_converter.create_multimedia_data_from_path(original_data, converter(url))
        return original_data

    def _convert_path_to_url(self, original_data: Any, converter: Callable[[str], str]):
        if self.format_converter.is_multimedia_format(original_data):
            path = self.format_converter.get_path_from_multimedia_data(original_data)
            # If original_data is not a path, return original_data directly.
            if path is None:
                return original_data
            return self.format_converter.create_multimedia_data_from_url(original_data, converter(path))
        return original_data

    def _process_content_recursively(self, content: Any, process_func: Callable):
        if isinstance(content, list):
            return [self._process_content_recursively(item, process_func) for item in content]
        elif isinstance(content, dict):
            if self.format_converter.is_multimedia_format(content):
                return process_func(original_data=content)
            else:
                return {k: self._process_content_recursively(v, process_func) for k, v in content.items()}
        else:
            return content
