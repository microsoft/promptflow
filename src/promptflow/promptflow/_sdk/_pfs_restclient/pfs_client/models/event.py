import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Type, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.event_attributes import EventAttributes


T = TypeVar("T", bound="Event")


@_attrs_define
class Event:
    """
    Attributes:
        name (str):
        timestamp (Union[Unset, datetime.datetime]):
        attributes (Union[Unset, EventAttributes]):
    """

    name: str
    timestamp: Union[Unset, datetime.datetime] = UNSET
    attributes: Union[Unset, "EventAttributes"] = UNSET
    additional_properties: Dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        name = self.name

        timestamp: Union[Unset, str] = UNSET
        if not isinstance(self.timestamp, Unset):
            timestamp = self.timestamp.isoformat()

        attributes: Union[Unset, Dict[str, Any]] = UNSET
        if not isinstance(self.attributes, Unset):
            attributes = self.attributes.to_dict()

        field_dict: Dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "name": name,
            }
        )
        if timestamp is not UNSET:
            field_dict["timestamp"] = timestamp
        if attributes is not UNSET:
            field_dict["attributes"] = attributes

        return field_dict

    @classmethod
    def from_dict(cls: Type[T], src_dict: Dict[str, Any]) -> T:
        from ..models.event_attributes import EventAttributes

        d = src_dict.copy()
        name = d.pop("name")

        _timestamp = d.pop("timestamp", UNSET)
        timestamp: Union[Unset, datetime.datetime]
        if isinstance(_timestamp, Unset):
            timestamp = UNSET
        else:
            timestamp = isoparse(_timestamp)

        _attributes = d.pop("attributes", UNSET)
        attributes: Union[Unset, EventAttributes]
        if isinstance(_attributes, Unset):
            attributes = UNSET
        else:
            attributes = EventAttributes.from_dict(_attributes)

        event = cls(
            name=name,
            timestamp=timestamp,
            attributes=attributes,
        )

        event.additional_properties = d
        return event

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
