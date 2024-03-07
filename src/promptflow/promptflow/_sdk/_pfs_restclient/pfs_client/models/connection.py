from typing import Any, Dict, List, Type, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="Connection")


@_attrs_define
class Connection:
    """
    Attributes:
        name (Union[Unset, str]):
        type (Union[Unset, str]):
        module (Union[Unset, str]):
        expiry_time (Union[Unset, str]):
        created_date (Union[Unset, str]):
        last_modified_date (Union[Unset, str]):
    """

    name: Union[Unset, str] = UNSET
    type: Union[Unset, str] = UNSET
    module: Union[Unset, str] = UNSET
    expiry_time: Union[Unset, str] = UNSET
    created_date: Union[Unset, str] = UNSET
    last_modified_date: Union[Unset, str] = UNSET
    additional_properties: Dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        name = self.name

        type = self.type

        module = self.module

        expiry_time = self.expiry_time

        created_date = self.created_date

        last_modified_date = self.last_modified_date

        field_dict: Dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if type is not UNSET:
            field_dict["type"] = type
        if module is not UNSET:
            field_dict["module"] = module
        if expiry_time is not UNSET:
            field_dict["expiry_time"] = expiry_time
        if created_date is not UNSET:
            field_dict["created_date"] = created_date
        if last_modified_date is not UNSET:
            field_dict["last_modified_date"] = last_modified_date

        return field_dict

    @classmethod
    def from_dict(cls: Type[T], src_dict: Dict[str, Any]) -> T:
        d = src_dict.copy()
        name = d.pop("name", UNSET)

        type = d.pop("type", UNSET)

        module = d.pop("module", UNSET)

        expiry_time = d.pop("expiry_time", UNSET)

        created_date = d.pop("created_date", UNSET)

        last_modified_date = d.pop("last_modified_date", UNSET)

        connection = cls(
            name=name,
            type=type,
            module=module,
            expiry_time=expiry_time,
            created_date=created_date,
            last_modified_date=last_modified_date,
        )

        connection.additional_properties = d
        return connection

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
