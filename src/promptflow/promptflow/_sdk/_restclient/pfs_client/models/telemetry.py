import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Type, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..models.telemetry_event_type import TelemetryEventType
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.metadata import Metadata


T = TypeVar("T", bound="Telemetry")


@_attrs_define
class Telemetry:
    """
    Attributes:
        event_type (TelemetryEventType): The event type of the telemetry. Example: Start.
        timestamp (datetime.datetime): The timestamp of the telemetry.
        first_call (Union[Unset, bool]): Whether current activity is the first activity in the call chain. Default:
            True.
        metadata (Union[Unset, Metadata]):
    """

    event_type: TelemetryEventType
    timestamp: datetime.datetime
    first_call: Union[Unset, bool] = True
    metadata: Union[Unset, "Metadata"] = UNSET
    additional_properties: Dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        event_type = self.event_type.value

        timestamp = self.timestamp.isoformat()

        first_call = self.first_call

        metadata: Union[Unset, Dict[str, Any]] = UNSET
        if not isinstance(self.metadata, Unset):
            metadata = self.metadata.to_dict()

        field_dict: Dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "eventType": event_type,
                "timestamp": timestamp,
            }
        )
        if first_call is not UNSET:
            field_dict["firstCall"] = first_call
        if metadata is not UNSET:
            field_dict["metadata"] = metadata

        return field_dict

    @classmethod
    def from_dict(cls: Type[T], src_dict: Dict[str, Any]) -> T:
        from ..models.metadata import Metadata

        d = src_dict.copy()
        event_type = TelemetryEventType(d.pop("eventType"))

        timestamp = isoparse(d.pop("timestamp"))

        first_call = d.pop("firstCall", UNSET)

        _metadata = d.pop("metadata", UNSET)
        metadata: Union[Unset, Metadata]
        if isinstance(_metadata, Unset):
            metadata = UNSET
        else:
            metadata = Metadata.from_dict(_metadata)

        telemetry = cls(
            event_type=event_type,
            timestamp=timestamp,
            first_call=first_call,
            metadata=metadata,
        )

        telemetry.additional_properties = d
        return telemetry

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
