# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from os import PathLike
from typing import Union
from urllib.parse import urlparse

import jwt


def is_arm_id(obj) -> bool:
    return isinstance(obj, str) and obj.startswith("azureml://")


def get_user_alias_from_credential(credential):
    token = credential.get_token("https://storage.azure.com/.default").token
    decode_json = jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
    try:
        email = decode_json["upn"]
        return email.split("@")[0]
    except Exception:
        # use oid when failed to get upn, e.g. service principal
        return decode_json["oid"]


def is_url(value: Union[PathLike, str]) -> bool:
    try:
        result = urlparse(str(value))
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def is_remote_uri(obj) -> bool:
    # return True if it's supported remote uri
    if isinstance(obj, str):
        if obj.startswith("azureml:"):
            # azureml: started, azureml:name:version, azureml://xxx
            return True
        elif is_url(obj):
            return True
    return False
