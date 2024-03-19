from typing import TYPE_CHECKING, Any, Dict, List, Type, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.resource_attributes import ResourceAttributes


T = TypeVar("T", bound="Resource")


@_attrs_define
class Resource:
    """
    Attributes:
        attributes (ResourceAttributes):
        schema_url (Union[Unset, str]):
    """

    attributes: "ResourceAttributes"
    schema_url: Union[Unset, str] = UNSET
    additional_properties: Dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        attributes = self.attributes.to_dict()

        schema_url = self.schema_url

        field_dict: Dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "attributes": attributes,
            }
        )
        if schema_url is not UNSET:
            field_dict["schema_url"] = schema_url

        return field_dict

    @classmethod
    def from_dict(cls: Type[T], src_dict: Dict[str, Any]) -> T:
        from ..models.resource_attributes import ResourceAttributes

        d = src_dict.copy()
        attributes = ResourceAttributes.from_dict(d.pop("attributes"))

        schema_url = d.pop("schema_url", UNSET)

        resource = cls(
            attributes=attributes,
            schema_url=schema_url,
        )

        resource.additional_properties = d
        return resource

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
