import collections
import json
import os
import re
from contextlib import contextmanager
from os import PathLike
from typing import IO, Any, AnyStr, Dict, Optional, Tuple, Union

import keyring
import yaml
from cryptography.fernet import Fernet
from filelock import FileLock
from jinja2 import Template
from marshmallow import ValidationError

from promptflow.sdk._constants import (
    KEYRING_ENCRYPTION_KEY_NAME,
    KEYRING_ENCRYPTION_LOCK_PATH,
    KEYRING_SYSTEM,
    Color,
    CommonYamlFields,
)


def snake_to_camel(name):
    return re.sub(r"(?:^|_)([a-z])", lambda x: x.group(1).upper(), name)


def find_type_in_override(params_override: Optional[list] = None) -> Optional[str]:
    params_override = params_override or []
    for override in params_override:
        if CommonYamlFields.TYPE in override:
            return override[CommonYamlFields.TYPE]
    return None


def load_yaml(source: Optional[Union[AnyStr, PathLike, IO]]) -> Dict:
    # null check - just return an empty dict.
    # Certain CLI commands rely on this behavior to produce a resource
    # via CLI, which is then populated through CLArgs.
    """Load a local YAML file.

    :param source: The relative or absolute path to the local file.
    :type source: str
    :return: A dictionary representation of the local file's contents.
    :rtype: Dict
    """
    # These imports can't be placed in at top file level because it will cause a circular import in
    # exceptions.py via _get_mfe_url_override

    if source is None:
        return {}

    # pylint: disable=redefined-builtin
    input = None
    must_open_file = False
    try:  # check source type by duck-typing it as an IOBase
        readable = source.readable()
        if not readable:  # source is misformatted stream or file
            msg = "File Permissions Error: The already-open \n\n inputted file is not readable."
            raise Exception(msg)
        # source is an already-open stream or file, we can read() from it directly.
        input = source
    except AttributeError:
        # source has no writable() function, assume it's a string or file path.
        must_open_file = True

    if must_open_file:  # If supplied a file path, open it.
        try:
            input = open(source, "r")
        except OSError:  # FileNotFoundError introduced in Python 3
            msg = "No such file or directory: {}"
            raise Exception(msg.format(source))
    # input should now be an readable file or stream. Parse it.
    cfg = {}
    try:
        cfg = yaml.safe_load(input)
    except yaml.YAMLError as e:
        msg = f"Error while parsing yaml file: {source} \n\n {str(e)}"
        raise Exception(msg)
    finally:
        if must_open_file:
            input.close()
    return cfg


# region Encryption

CUSTOMIZED_ENCRYPTION_KEY_IN_KEY_RING = None


@contextmanager
def use_customized_encryption_key(encryption_key: str):
    global CUSTOMIZED_ENCRYPTION_KEY_IN_KEY_RING

    CUSTOMIZED_ENCRYPTION_KEY_IN_KEY_RING = encryption_key
    yield
    CUSTOMIZED_ENCRYPTION_KEY_IN_KEY_RING = None


def set_encryption_key(encryption_key: Union[str, bytes]):
    if isinstance(encryption_key, bytes):
        encryption_key = encryption_key.decode("utf-8")
    keyring.set_password("promptflow", "encryption_key", encryption_key)


_encryption_key_lock = FileLock(KEYRING_ENCRYPTION_LOCK_PATH)


def get_encryption_key(generate_if_not_found: bool = False) -> str:
    global CUSTOMIZED_ENCRYPTION_KEY_IN_KEY_RING
    if CUSTOMIZED_ENCRYPTION_KEY_IN_KEY_RING is not None:
        encryption_key = CUSTOMIZED_ENCRYPTION_KEY_IN_KEY_RING
    else:
        encryption_key = keyring.get_password(KEYRING_SYSTEM, KEYRING_ENCRYPTION_KEY_NAME)

    if encryption_key is not None or not generate_if_not_found:
        return encryption_key
    _encryption_key_lock.acquire()
    encryption_key = keyring.get_password(KEYRING_SYSTEM, KEYRING_ENCRYPTION_KEY_NAME)
    if encryption_key is not None:
        return encryption_key
    try:
        encryption_key = Fernet.generate_key().decode("utf-8")
        keyring.set_password(KEYRING_SYSTEM, KEYRING_ENCRYPTION_KEY_NAME, encryption_key)
    finally:
        _encryption_key_lock.release()
    return encryption_key


def encrypt_secret_value(secret_value):
    encryption_key = get_encryption_key(generate_if_not_found=True)
    fernet_client = Fernet(encryption_key)
    token = fernet_client.encrypt(secret_value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret_value(connection_name, encrypted_secret_value):
    encryption_key = get_encryption_key()
    if encryption_key is None:
        raise Exception("Encryption key not found in keyring.")
    fernet_client = Fernet(encryption_key)
    try:
        return fernet_client.decrypt(encrypted_secret_value.encode("utf-8")).decode("utf-8")
    except Exception as e:
        if len(encrypted_secret_value) < 57:
            # This is to workaround old custom secrets that are not encrypted with Fernet.
            # Fernet token: https://github.com/fernet/spec/blob/master/Spec.md
            # Format: Version ‖ Timestamp ‖ IV ‖ Ciphertext ‖ HMAC
            # Version: 8 bits, Timestamp: 64 bits, IV: 128 bits, HMAC: 256 bits,
            # Ciphertext variable length, multiple of 128 bits
            # So the minimum length of a Fernet token is 57 bytes
            print_yellow_warning(
                f"Warning: Please recreate connection {connection_name} due to a security issue in the old sdk version."
            )
            return encrypted_secret_value
        raise Exception(
            f"Decrypt connection {connection_name} secret failed: {str(e)}. "
            f"If you have ever changed your encryption key manually, "
            f"please revert it back to the original one, or delete all connections and re-create them."
        )


# endregion


def dump_yaml(*args, **kwargs):
    """A thin wrapper over yaml.dump which forces `OrderedDict`s to be serialized as mappings.

    Other behaviors identically to yaml.dump
    """

    class OrderedDumper(yaml.Dumper):
        """A modified yaml serializer that forces pyyaml to represent an OrderedDict as a mapping instead of a
        sequence."""

    OrderedDumper.add_representer(collections.OrderedDict, yaml.representer.SafeRepresenter.represent_dict)
    return yaml.dump(*args, Dumper=OrderedDumper, **kwargs)


def decorate_validation_error(schema: Any, pretty_error: str, additional_message: str = "") -> str:
    return f"Validation for {schema.__name__} failed:\n\n {pretty_error} \n\n {additional_message}"


def load_from_dict(schema: Any, data: Dict, context: Dict, additional_message: str = "", **kwargs):
    try:
        return schema(context=context).load(data, **kwargs)
    except ValidationError as e:
        pretty_error = json.dumps(e.normalized_messages(), indent=2)
        raise ValidationError(decorate_validation_error(schema, pretty_error, additional_message))


def parse_variant(variant: str) -> Tuple[str, str]:
    variant_regex = r"\${([^.]+).([^}]+)}"
    match = re.match(variant_regex, variant)
    if match:
        return match.group(1), match.group(2)
    else:
        raise ValueError(f"Invalid variant format: {variant}, variant should be in format of ${{TUNING_NODE.VARIANT}}")


def _match_reference(env_val: str):
    env_val = env_val.strip()
    m = re.match(r"^\$\{([^.]+)\.([^.]+)}$", env_val)
    if not m:
        return None, None
    name, key = m.groups()
    return name, key


# !!! Attention!!!: Please make sure you have contact with PRS team before changing the interface.
def get_used_connection_names_from_environment_variables():
    """The function will get all potential related connection names from current environment variables.
    for example, if part of env var is
    {
      "ENV_VAR_1": "${my_connection.key}",
      "ENV_VAR_2": "${my_connection.key2}",
      "ENV_VAR_3": "${my_connection2.key}",
    }
    The function will return {"my_connection", "my_connection2"}.
    """
    return get_used_connection_names_from_dict(os.environ)


def get_used_connection_names_from_dict(connection_dict: dict):
    connection_names = set()
    for key, val in connection_dict.items():
        connection_name, _ = _match_reference(val)
        if connection_name:
            connection_names.add(connection_name)

    return connection_names


# !!! Attention!!!: Please make sure you have contact with PRS team before changing the interface.
def update_environment_variables_with_connections(built_connections):
    """The function will result env var value ${my_connection.key} to the real connection keys."""
    return update_dict_value_with_connections(built_connections, os.environ)


def update_dict_value_with_connections(built_connections, connection_dict: dict):
    for key, val in connection_dict.items():
        connection_name, connection_key = _match_reference(val)
        if connection_name is None:
            continue
        if connection_name not in built_connections:
            continue
        if connection_key not in built_connections[connection_name]["value"]:
            continue
        connection_dict[key] = built_connections[connection_name]["value"][connection_key]


def in_jupyter_notebook() -> bool:
    """
    Checks if user is using a Jupyter Notebook. This is necessary because logging is not allowed in
    non-Jupyter contexts.

    Adapted from https://stackoverflow.com/a/22424821
    """
    try:  # cspell:ignore ipython
        from IPython import get_ipython

        if "IPKernelApp" not in get_ipython().config:
            return False
    except ImportError:
        return False
    except AttributeError:
        return False
    return True


def render_jinja_template(template_path, *, trim_blocks=True, keep_trailing_newline=True, **kwargs):
    with open(template_path, "r") as f:
        template = Template(f.read(), trim_blocks=trim_blocks, keep_trailing_newline=keep_trailing_newline)
    return template.render(**kwargs)


def print_yellow_warning(message):
    print(Color.YELLOW + message + Color.END)


def safe_parse_object_list(obj_list, parser, message_generator):
    results = []
    for obj in obj_list:
        try:
            results.append(parser(obj))
        except Exception as e:
            extended_message = f"{message_generator(obj)} Error: {type(e).__name__}, {str(e)}"
            print_yellow_warning(extended_message)
    return results


def incremental_print(log: str, printed: int, fileout) -> int:
    count = 0
    for line in log.splitlines():
        if count >= printed:
            fileout.write(line + "\n")
            printed += 1
        count += 1
    return printed
