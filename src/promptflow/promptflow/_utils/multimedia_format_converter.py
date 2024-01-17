from functools import partial
from pathlib import Path
from typing import Any, Callable

from promptflow._utils.multimedia_utils import _get_multimedia_info, is_multimedia_dict


# Format converter to switch multimedia expression between path and url for each contract version.
class AbstractMultimediaFormatConverter:
    # Check if the original_data is a multimedia format according to current contract version.
    def is_valid_format(self, original_data: Any):
        raise NotImplementedError()

    # Get the path from multimedia data. Below is example for 20231201 version:
    # {"data:image/jpg;path": "logo.jpg"} -> "logo.jpg"
    def get_path_from_data(self, original_data: Any):
        raise NotImplementedError()

    # Get the url from multimedia data. Below is example for 20231201 version:
    # {"data:image/jpg;url": "https://example.com/logo.jpg"} -> "https://example.com/logo.jpg"
    def get_url_from_data(self, original_data: Any):
        raise NotImplementedError()

    # Create multimedia data from path. Below is example for 20231201 version:
    # original_data + "new_logo.jpg" -> {"data:image/jpg;path": "new_logo.jpg"}
    def create_data_from_path(self, original_data: Any, path: str):
        raise NotImplementedError()

    # Create multimedia data from url. Below is example for 20231201 version:
    # original_data + "https://example.com/logo.jpg" -> {"data:image/jpg;url": "https://example.com/logo.jpg"}
    def create_data_from_url(self, original_data: Any, url: str):
        raise NotImplementedError()


# 20231201 version is our first contract's version, supports text and images (path/url/base64).
# 20231201 is version number customer assign in yaml file.
# Path format example: {"data:image/jpg;path": "logo.jpg"}
# Url format example: {"data:image/jpg;url": "https://example.com/logo.jpg"}
# Base64 format example: {"data:image/jpg;base64": "base64 string"}
class MultimediaFormatConverter20231201(AbstractMultimediaFormatConverter):
    PATH_RESOURCE_TYPE = "path"
    URL_RESOURCE_TYPE = "url"

    def is_valid_format(self, original_data: Any):
        return isinstance(original_data, dict) and is_multimedia_dict(original_data)

    def _get_path_or_url_from_multimedia_data(self, original_data: Any, resource_type: str):
        if self.is_valid_format(original_data):
            for key in original_data:
                _, resource = _get_multimedia_info(key)
                if resource == resource_type:
                    return original_data[key]
        return None

    def get_path_from_data(self, original_data: Any):
        return self._get_path_or_url_from_multimedia_data(original_data, self.PATH_RESOURCE_TYPE)

    def get_url_from_data(self, original_data: Any):
        return self._get_path_or_url_from_multimedia_data(original_data, self.URL_RESOURCE_TYPE)

    def _create_multimedia_data_from_path_or_url(self, original_data: Any, value: str, resource_type: str):
        if self.is_valid_format(original_data):
            for key in original_data:
                format, _ = _get_multimedia_info(key)
                return {f"data:image/{format};{resource_type}": value}
        return None

    def create_data_from_path(self, original_data: Any, path: str):
        return self._create_multimedia_data_from_path_or_url(original_data, path, self.PATH_RESOURCE_TYPE)

    def create_data_from_url(self, original_data: Any, url: str):
        return self._create_multimedia_data_from_path_or_url(original_data, url, self.URL_RESOURCE_TYPE)


# Client side should implement the following two converters to convert between url and path.
class AbstractUrlToPathConverter:
    def should_process(self, url: str) -> bool:
        """
        Determine whether the URL should be processed or not.
        For example, public access urls don't need to be processed.

        :param url: The URL to be processed.
        :type url: str
        :return: True if the URL should be processed, False otherwise.
        :rtype: bool
        """
        return True

    def convert(self, url: str) -> str:
        """
        Convert the URL to a path.

        :param url: The URL to be converted.
        :type url: str
        :return: The converted path.
        :rtype: str
        """
        return url


class AbstractPathToUrlConverter:
    def should_process(self, path: str) -> bool:
        """
        Determine whether the path should be processed or not.

        :param path: The path to be processed.
        :type path: str
        :return: True if the path should be processed, False otherwise.
        :rtype: bool
        """
        # Add your logic here to determine whether the path should be processed or not
        return True

    def convert(self, path: str) -> str:
        """
        Convert the path to a URL.

        :param path: The path to be converted.
        :type path: str
        :return: The converted URL.
        :rtype: str
        """
        # Add your logic here to convert the path to a URL
        return path


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

    def convert_url_to_path_recursively(self, content: Any, url_to_path_converter: AbstractUrlToPathConverter):
        """
        Recursively converts URLs to paths in content that may contain multimedia data.

        :param content: The object that may contain multimedia data.
        :type content: Any
        :param url_to_path_converter: The converter to convert URLs to paths. May also include file downloading logic.
        :type url_to_path_converter: AbstractUrlToPathConverter
        :return: The data with URLs converted to paths.
        :rtype: Any
        """
        process_func = partial(self._convert_url_to_path, converter=url_to_path_converter)
        return self._process_content_recursively(content, process_func=process_func)

    def convert_path_to_url_recursively(self, content: Any, path_to_url_converter: AbstractPathToUrlConverter):
        """
        Recursively converts paths to URLs in content that may contain multimedia data.

        :param content: The object that may contain multimedia data.
        :type content: Any
        :param path_to_url_converter: The converter to convert paths to URLs. May also include file uploading logic.
        :type path_to_url_converter: AbstractPathToUrlConverter
        :return: The data with paths converted to URLs.
        :rtype: Any
        """
        process_func = partial(self._convert_path_to_url, converter=path_to_url_converter)
        return self._process_content_recursively(content, process_func=process_func)

    def _convert_url_to_path(self, original_data: Any, converter: AbstractPathToUrlConverter):
        if self.format_converter.is_valid_format(original_data):
            url = self.format_converter.get_url_from_data(original_data)
            # When can't extract url from original_data, return original_data directly.
            if url is None:
                return original_data
            # If original_data is not a url, return original_data directly.
            # May don't need to convert all url to path, so need to check is_processed or not.
            if not converter.should_process(url):
                return original_data
            path = converter.convert(url)
            return self.format_converter.create_data_from_path(original_data, path)
        return original_data

    def _convert_path_to_url(self, original_data: Any, converter: AbstractPathToUrlConverter):
        if self.format_converter.is_valid_format(original_data):
            path = self.format_converter.get_path_from_data(original_data)
            # When can't extract path from original_data, return original_data directly.
            if path is None:
                return original_data
            # If original_data is not a path, return original_data directly.
            if not converter.should_process(path):
                return original_data
            url = converter.convert(path)
            return self.format_converter.create_data_from_url(original_data, url)
        return original_data

    def _process_content_recursively(self, content: Any, process_func: Callable):
        if isinstance(content, list):
            return [self._process_content_recursively(item, process_func) for item in content]
        elif isinstance(content, dict):
            if self.format_converter.is_valid_format(content):
                return process_func(original_data=content)
            else:
                return {k: self._process_content_recursively(v, process_func) for k, v in content.items()}
        else:
            return content
