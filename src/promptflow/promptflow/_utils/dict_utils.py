# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


def get_value_by_key_path(dct, key_path, default_value=None):
    """Given a dict, get value from key path.

    >>> dct = {
    ...     'Beijing': {
    ...         'Haidian': {
    ...             'ZipCode': '110108',
    ...         }
    ...     }
    ... }
    >>> get_value_by_key_path(dct, 'Beijing/Haidian/ZipCode')
    '110108'
    """
    if not key_path:
        raise ValueError("key_path must not be empty")

    segments = key_path.split("/")
    final_flag = object()
    segments.append(final_flag)

    walked = []

    cur_obj = dct
    for seg in segments:
        # If current segment is final_flag,
        # the cur_obj is the object that the given key path points to.
        # Simply return it as result.
        if seg is final_flag:
            # return default_value if cur_obj is None
            return default_value if cur_obj is None else cur_obj

        # If still in the middle of key path, when cur_obj is not a dict,
        # will fail to locate the values
        if not isinstance(cur_obj, dict):
            # TODO: maybe add options to raise exceptions here in the future
            return default_value

        # Move to next segment
        cur_obj = cur_obj.get(seg)
        walked.append(seg)

    raise Exception(f"Failed to get value by key path: {key_path}")
