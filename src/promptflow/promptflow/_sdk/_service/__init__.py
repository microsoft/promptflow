# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

try:
    from flask_restx import Api, Namespace, Resource, fields  # noqa: F401
except ImportError as ex:
    from promptflow.exceptions import UserErrorException

    raise UserErrorException(f"Please try 'pip install promptflow[pfs]' to install dependency, {ex.msg}.")
