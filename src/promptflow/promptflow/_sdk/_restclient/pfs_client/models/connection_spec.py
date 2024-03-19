from typing import TYPE_CHECKING, Any, Dict, List, Type, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.connection_config_spec import ConnectionConfigSpec


T = TypeVar("T", bound="ConnectionSpec")


@_attrs_define
class ConnectionSpec:
    """
    Attributes:
        connection_type (Union[Unset, str]):
        config_spec (Union[Unset, List['ConnectionConfigSpec']]):
    """

    connection_type: Union[Unset, str] = UNSET
    config_spec: Union[Unset, List["ConnectionConfigSpec"]] = UNSET
    additional_properties: Dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        connection_type = self.connection_type

        config_spec: Union[Unset, List[Dict[str, Any]]] = UNSET
        if not isinstance(self.config_spec, Unset):
            config_spec = []
            for config_spec_item_data in self.config_spec:
                config_spec_item = config_spec_item_data.to_dict()
                config_spec.append(config_spec_item)

        field_dict: Dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if connection_type is not UNSET:
            field_dict["connection_type"] = connection_type
        if config_spec is not UNSET:
            field_dict["config_spec"] = config_spec

        return field_dict

    @classmethod
    def from_dict(cls: Type[T], src_dict: Dict[str, Any]) -> T:
        from ..models.connection_config_spec import ConnectionConfigSpec

        d = src_dict.copy()
        connection_type = d.pop("connection_type", UNSET)

        config_spec = []
        _config_spec = d.pop("config_spec", UNSET)
        for config_spec_item_data in _config_spec or []:
            config_spec_item = ConnectionConfigSpec.from_dict(config_spec_item_data)

            config_spec.append(config_spec_item)

        connection_spec = cls(
            connection_type=connection_type,
            config_spec=config_spec,
        )

        connection_spec.additional_properties = d
        return connection_spec

    @property
    def additional_keys(self) -> List[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
