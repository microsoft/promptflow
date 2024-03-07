from typing import TYPE_CHECKING, Any, Dict, List, Type, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.context import Context
    from ..models.link_attributes import LinkAttributes


T = TypeVar("T", bound="Link")


@_attrs_define
class Link:
    """
    Attributes:
        context (Union[Unset, Context]):
        attributes (Union[Unset, LinkAttributes]):
    """

    context: Union[Unset, "Context"] = UNSET
    attributes: Union[Unset, "LinkAttributes"] = UNSET
    additional_properties: Dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        context: Union[Unset, Dict[str, Any]] = UNSET
        if not isinstance(self.context, Unset):
            context = self.context.to_dict()

        attributes: Union[Unset, Dict[str, Any]] = UNSET
        if not isinstance(self.attributes, Unset):
            attributes = self.attributes.to_dict()

        field_dict: Dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if context is not UNSET:
            field_dict["context"] = context
        if attributes is not UNSET:
            field_dict["attributes"] = attributes

        return field_dict

    @classmethod
    def from_dict(cls: Type[T], src_dict: Dict[str, Any]) -> T:
        from ..models.context import Context
        from ..models.link_attributes import LinkAttributes

        d = src_dict.copy()
        _context = d.pop("context", UNSET)
        context: Union[Unset, Context]
        if isinstance(_context, Unset):
            context = UNSET
        else:
            context = Context.from_dict(_context)

        _attributes = d.pop("attributes", UNSET)
        attributes: Union[Unset, LinkAttributes]
        if isinstance(_attributes, Unset):
            attributes = UNSET
        else:
            attributes = LinkAttributes.from_dict(_attributes)

        link = cls(
            context=context,
            attributes=attributes,
        )

        link.additional_properties = d
        return link

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
