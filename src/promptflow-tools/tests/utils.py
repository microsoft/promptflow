import json


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __getattr__(self, item):
        if item in self:
            return self.__getitem__(item)
        return super().__getattribute__(item)


def is_json_serializable(data, function_name):
    try:
        json.dumps(data)
    except TypeError:
        raise TypeError(f"{function_name} output is not JSON serializable!")
