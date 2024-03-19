import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Type, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.context import Context
    from ..models.event import Event
    from ..models.link import Link
    from ..models.resource import Resource
    from ..models.span_attributes import SpanAttributes
    from ..models.status import Status


T = TypeVar("T", bound="Span")


@_attrs_define
class Span:
    """
    Attributes:
        name (str):
        context (Context):
        kind (str):
        attributes (SpanAttributes):
        resource (Resource):
        parent_id (Union[Unset, str]):
        start_time (Union[Unset, datetime.datetime]):
        end_time (Union[Unset, datetime.datetime]):
        status (Union[Unset, Status]):
        events (Union[Unset, List['Event']]):
        links (Union[Unset, List['Link']]):
    """

    name: str
    context: "Context"
    kind: str
    attributes: "SpanAttributes"
    resource: "Resource"
    parent_id: Union[Unset, str] = UNSET
    start_time: Union[Unset, datetime.datetime] = UNSET
    end_time: Union[Unset, datetime.datetime] = UNSET
    status: Union[Unset, "Status"] = UNSET
    events: Union[Unset, List["Event"]] = UNSET
    links: Union[Unset, List["Link"]] = UNSET
    additional_properties: Dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        name = self.name

        context = self.context.to_dict()

        kind = self.kind

        attributes = self.attributes.to_dict()

        resource = self.resource.to_dict()

        parent_id = self.parent_id

        start_time: Union[Unset, str] = UNSET
        if not isinstance(self.start_time, Unset):
            start_time = self.start_time.isoformat()

        end_time: Union[Unset, str] = UNSET
        if not isinstance(self.end_time, Unset):
            end_time = self.end_time.isoformat()

        status: Union[Unset, Dict[str, Any]] = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.to_dict()

        events: Union[Unset, List[Dict[str, Any]]] = UNSET
        if not isinstance(self.events, Unset):
            events = []
            for events_item_data in self.events:
                events_item = events_item_data.to_dict()
                events.append(events_item)

        links: Union[Unset, List[Dict[str, Any]]] = UNSET
        if not isinstance(self.links, Unset):
            links = []
            for links_item_data in self.links:
                links_item = links_item_data.to_dict()
                links.append(links_item)

        field_dict: Dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "name": name,
                "context": context,
                "kind": kind,
                "attributes": attributes,
                "resource": resource,
            }
        )
        if parent_id is not UNSET:
            field_dict["parent_id"] = parent_id
        if start_time is not UNSET:
            field_dict["start_time"] = start_time
        if end_time is not UNSET:
            field_dict["end_time"] = end_time
        if status is not UNSET:
            field_dict["status"] = status
        if events is not UNSET:
            field_dict["events"] = events
        if links is not UNSET:
            field_dict["links"] = links

        return field_dict

    @classmethod
    def from_dict(cls: Type[T], src_dict: Dict[str, Any]) -> T:
        from ..models.context import Context
        from ..models.event import Event
        from ..models.link import Link
        from ..models.resource import Resource
        from ..models.span_attributes import SpanAttributes
        from ..models.status import Status

        d = src_dict.copy()
        name = d.pop("name")

        context = Context.from_dict(d.pop("context"))

        kind = d.pop("kind")

        attributes = SpanAttributes.from_dict(d.pop("attributes"))

        resource = Resource.from_dict(d.pop("resource"))

        parent_id = d.pop("parent_id", UNSET)

        _start_time = d.pop("start_time", UNSET)
        start_time: Union[Unset, datetime.datetime]
        if isinstance(_start_time, Unset):
            start_time = UNSET
        else:
            start_time = isoparse(_start_time)

        _end_time = d.pop("end_time", UNSET)
        end_time: Union[Unset, datetime.datetime]
        if isinstance(_end_time, Unset):
            end_time = UNSET
        else:
            end_time = isoparse(_end_time)

        _status = d.pop("status", UNSET)
        status: Union[Unset, Status]
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = Status.from_dict(_status)

        events = []
        _events = d.pop("events", UNSET)
        for events_item_data in _events or []:
            events_item = Event.from_dict(events_item_data)

            events.append(events_item)

        links = []
        _links = d.pop("links", UNSET)
        for links_item_data in _links or []:
            links_item = Link.from_dict(links_item_data)

            links.append(links_item)

        span = cls(
            name=name,
            context=context,
            kind=kind,
            attributes=attributes,
            resource=resource,
            parent_id=parent_id,
            start_time=start_time,
            end_time=end_time,
            status=status,
            events=events,
            links=links,
        )

        span.additional_properties = d
        return span

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
