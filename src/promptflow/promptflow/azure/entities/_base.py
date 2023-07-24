# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import abc
from os import PathLike
from pathlib import Path
from typing import Dict, Optional, Union

from azure.ai.ml._utils.utils import dump_yaml
from azure.ai.ml.constants._common import BASE_PATH_CONTEXT_KEY, PARAMS_OVERRIDE_KEY
from azure.ai.ml.entities._util import load_from_dict


class Base(abc.ABC):
    @classmethod
    @abc.abstractmethod
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
    @abc.abstractmethod
    def _get_schema_cls(self):
        pass

    @abc.abstractmethod
    def _to_rest_object(self):
        pass

    @classmethod
    @abc.abstractmethod
    def _from_rest_object(cls, flow):
        pass

    def _to_dict(self) -> Dict:
        schema_cls = self._get_schema_cls()
        return schema_cls(context={BASE_PATH_CONTEXT_KEY: "./"}).dump(self)

    def _to_yaml(self) -> str:
        return dump_yaml(self._to_dict(), sort_keys=False)

    def __str__(self):
        try:
            return self._to_yaml()
        except BaseException:  # pylint: disable=broad-except
            return super(Base, self).__str__()

    @classmethod
    def _load_from_dict(cls, data: Dict, context: Dict, additional_message: str, **kwargs):
        schema_cls = cls._get_schema_cls()
        loaded_data = load_from_dict(schema_cls, data, context, additional_message, **kwargs)
        return cls(base_path=context[BASE_PATH_CONTEXT_KEY], **loaded_data)

    @classmethod
    def _load(
            cls,
            data: Optional[Dict] = None,
            yaml_path: Optional[Union[PathLike, str]] = None,
            params_override: Optional[list] = None,
            **kwargs,
    ):
        context = {
            BASE_PATH_CONTEXT_KEY: Path(yaml_path).parent if yaml_path else Path("./"),
            PARAMS_OVERRIDE_KEY: params_override,
        }
        return cls._load_from_dict(
            data=data,
            context=context,
            additional_message="Please check the documentation for the correct format.",
            **kwargs,
        )
