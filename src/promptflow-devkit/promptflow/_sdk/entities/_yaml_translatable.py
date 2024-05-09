# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import abc
from typing import Dict, Optional

from promptflow._sdk._constants import BASE_PATH_CONTEXT_KEY, CommonYamlFields
from promptflow._sdk._utilities.general_utils import load_from_dict
from promptflow._utils.yaml_utils import dump_yaml


class YAMLTranslatableMixin(abc.ABC):
    @classmethod
    # pylint: disable=unused-argument
    def _resolve_cls_and_type(cls, data, params_override: Optional[list]):
        """Resolve the class to use for deserializing the data. Return current class if no override is provided.
        :param data: Data to deserialize.
        :type data: dict
        :param params_override: Parameters to override, defaults to None
        :type params_override: typing.Optional[list]
        :return: Class to use for deserializing the data & its "type". Type will be None if no override is provided.
        :rtype: tuple[class, typing.Optional[str]]
        """

    @classmethod
    def _get_schema_cls(self):
        pass

    def _to_dict(self) -> Dict:
        schema_cls = self._get_schema_cls()
        return schema_cls(context={BASE_PATH_CONTEXT_KEY: "./"}).dump(self)

    def _to_yaml(self) -> str:
        return dump_yaml(self._to_dict())

    def __str__(self):
        try:
            return self._to_yaml()
        except BaseException:  # pylint: disable=broad-except
            return super(YAMLTranslatableMixin, self).__str__()

    @classmethod
    def _load_from_dict(cls, data: Dict, context: Dict, additional_message: str, **kwargs):
        schema_cls = cls._get_schema_cls()
        loaded_data = load_from_dict(schema_cls, data, context, additional_message, **kwargs)
        # pop the type field since it already exists in class init
        loaded_data.pop(CommonYamlFields.TYPE, None)
        return cls(base_path=context[BASE_PATH_CONTEXT_KEY], **loaded_data)
