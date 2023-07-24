import jwt


def is_arm_id(obj) -> bool:
    return isinstance(obj, str) and obj.startswith("azureml://")


def get_user_alias_from_credential(credential):
    token = credential.get_token("https://storage.azure.com/.default").token
    decode_json = jwt.decode(token, options={'verify_signature': False, 'verify_aud': False})
    try:
        email = decode_json["upn"]
        return email.split("@")[0]
    except Exception:
        # use oid when failed to get upn, e.g. service principal
        return decode_json["oid"]
