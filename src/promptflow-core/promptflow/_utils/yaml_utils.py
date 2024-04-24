from io import StringIO
from os import PathLike
from typing import IO, AnyStr, Dict, Optional, Union

from ruamel.yaml import YAML, YAMLError

from promptflow._constants import DEFAULT_ENCODING
from promptflow._utils._errors import YamlParseError
from promptflow.exceptions import UserErrorException


def load_yaml(source: Optional[Union[AnyStr, PathLike, IO]]) -> Dict:
    # null check - just return an empty dict.
    # Certain CLI commands rely on this behavior to produce a resource
    # via CLI, which is then populated through CLArgs.
    """Load a local YAML file or a readable stream object.

    .. note::

        1. For a local file yaml

        .. code-block:: python

            yaml_path = "path/to/yaml"
            content = load_yaml(yaml_path)

        2. For a readable stream object

        .. code-block:: python

            with open("path/to/yaml", "r", encoding="utf-8") as f:
                content = load_yaml(f)


    :param source: The relative or absolute path to the local file, or a readable stream object.
    :type source: str
    :return: A dictionary representation of the local file's contents.
    :rtype: Dict
    """

    if source is None:
        return {}

    # pylint: disable=redefined-builtin
    input = None
    must_open_file = False
    try:  # check source type by duck-typing it as an IOBase
        readable = source.readable()
        if not readable:  # source is misformatted stream or file
            msg = "File Permissions Error: The already-open \n\n inputted file is not readable."
            raise PermissionError(msg)
        # source is an already-open stream or file, we can read() from it directly.
        input = source
    except AttributeError:
        # source has no writable() function, assume it's a string or file path.
        must_open_file = True

    if must_open_file:  # If supplied a file path, open it.
        try:
            input = open(source, "r", encoding=DEFAULT_ENCODING)
        except OSError:  # FileNotFoundError introduced in Python 3
            e = FileNotFoundError("No such file or directory: {}".format(source))
            raise UserErrorException(str(e), privacy_info=[str(source)]) from e
    # input should now be a readable file or stream. Parse it.
    try:
        yaml = YAML()
        yaml.preserve_quotes = True
        cfg = yaml.load(input)
    except YAMLError as e:
        msg = f"Error while parsing yaml file: {source} \n\n {str(e)}"
        raise YAMLError(msg)
    finally:
        if must_open_file:
            input.close()
    if cfg is None:
        return {}
    return cfg


def load_yaml_string(yaml_string: str):
    """Load a yaml string.

    .. code-block:: python

        yaml_string = "some yaml string"
        object = load_yaml_string(yaml_string)


    :param yaml_string: A yaml string.
    :type yaml_string: str
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    return yaml.load(yaml_string)


def dump_yaml(*args, **kwargs):
    """Dump data to a yaml string or stream.

    .. note::

        1. Dump to a yaml string

        .. code-block:: python

            data = {"key": "value"}
            yaml_string = dump_yaml(data)

        2. Dump to a stream

        .. code-block:: python

            data = {"key": "value"}
            with open("path/to/yaml", "w", encoding="utf-8") as f:
                dump_yaml(data, f)
    """
    yaml = YAML()
    yaml.default_flow_style = False
    # when using with no stream parameter but just the data, dump to yaml string and return
    if len(args) == 1:
        string_stream = StringIO()
        yaml.dump(args[0], string_stream, **kwargs)
        output_string = string_stream.getvalue()
        string_stream.close()
        return output_string
    # when using with stream parameter, dump to stream. e.g.:
    # open('test.yaml', 'w', encoding='utf-8') as f:
    #     dump_yaml(data, f)
    elif len(args) == 2:
        return yaml.dump(*args, **kwargs)
    else:
        raise YamlParseError("Only 1 or 2 positional arguments are allowed for dump yaml util function.")
