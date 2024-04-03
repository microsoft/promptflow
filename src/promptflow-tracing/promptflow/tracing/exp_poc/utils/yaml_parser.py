from dataclasses import is_dataclass, fields
from ruamel.yaml import YAML
from typing import Any, get_origin


class YamlParser:

    @classmethod
    def load_to_dataclass(
        cls,
        dataclass_type: type,
        file_content: str
    ) -> Any:
        yaml = YAML()
        yaml_config = yaml.load(file_content)
        return cls.__dict_to_dataclass(dataclass_type, yaml_config)

    @staticmethod
    def __dict_to_dataclass(dataclass_type: type, data: dict):
        obj = dataclass_type()
        field_list = fields(dataclass_type)
        for field in field_list:
            if field.name not in data:
                continue
            if is_dataclass(field.type):
                setattr(
                    obj,
                    field.name,
                    YamlParser.__dict_to_dataclass(
                        field.type,
                        data[field.name]
                    )
                )
            if get_origin(field.type) is list:
                element_type = field.type.__args__[0]
                setattr(
                    obj,
                    field.name,
                    [
                        YamlParser.__dict_to_dataclass(
                            element_type,
                            element
                        )
                        for element in data[field.name]
                    ]
                )
            else:
                setattr(obj, field.name, data[field.name])
        return obj
