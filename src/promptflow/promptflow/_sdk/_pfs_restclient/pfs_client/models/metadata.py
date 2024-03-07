from typing import Any, Dict, List, Type, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.metadata_activity_name import MetadataActivityName
from ..models.metadata_completion_status import MetadataCompletionStatus
from ..types import UNSET, Unset

T = TypeVar("T", bound="Metadata")


@_attrs_define
class Metadata:
    """
    Attributes:
        activity_name (MetadataActivityName): The name of the activity. Example: pf.flow.test.
        activity_type (str): The type of the activity.
        completion_status (Union[Unset, MetadataCompletionStatus]): The completion status of the activity. Example:
            Success.
        duration_ms (Union[Unset, int]): The duration of the activity in milliseconds.
        error_category (Union[Unset, str]): The error category of the activity.
        error_type (Union[Unset, str]): The error type of the activity.
        error_target (Union[Unset, str]): The error target of the activity.
        error_message (Union[Unset, str]): The error message of the activity.
        error_details (Union[Unset, str]): The error details of the activity.
    """

    activity_name: MetadataActivityName
    activity_type: str
    completion_status: Union[Unset, MetadataCompletionStatus] = UNSET
    duration_ms: Union[Unset, int] = UNSET
    error_category: Union[Unset, str] = UNSET
    error_type: Union[Unset, str] = UNSET
    error_target: Union[Unset, str] = UNSET
    error_message: Union[Unset, str] = UNSET
    error_details: Union[Unset, str] = UNSET
    additional_properties: Dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        activity_name = self.activity_name.value

        activity_type = self.activity_type

        completion_status: Union[Unset, str] = UNSET
        if not isinstance(self.completion_status, Unset):
            completion_status = self.completion_status.value

        duration_ms = self.duration_ms

        error_category = self.error_category

        error_type = self.error_type

        error_target = self.error_target

        error_message = self.error_message

        error_details = self.error_details

        field_dict: Dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "activityName": activity_name,
                "activityType": activity_type,
            }
        )
        if completion_status is not UNSET:
            field_dict["completionStatus"] = completion_status
        if duration_ms is not UNSET:
            field_dict["durationMs"] = duration_ms
        if error_category is not UNSET:
            field_dict["errorCategory"] = error_category
        if error_type is not UNSET:
            field_dict["errorType"] = error_type
        if error_target is not UNSET:
            field_dict["errorTarget"] = error_target
        if error_message is not UNSET:
            field_dict["errorMessage"] = error_message
        if error_details is not UNSET:
            field_dict["errorDetails"] = error_details

        return field_dict

    @classmethod
    def from_dict(cls: Type[T], src_dict: Dict[str, Any]) -> T:
        d = src_dict.copy()
        activity_name = MetadataActivityName(d.pop("activityName"))

        activity_type = d.pop("activityType")

        _completion_status = d.pop("completionStatus", UNSET)
        completion_status: Union[Unset, MetadataCompletionStatus]
        if isinstance(_completion_status, Unset):
            completion_status = UNSET
        else:
            completion_status = MetadataCompletionStatus(_completion_status)

        duration_ms = d.pop("durationMs", UNSET)

        error_category = d.pop("errorCategory", UNSET)

        error_type = d.pop("errorType", UNSET)

        error_target = d.pop("errorTarget", UNSET)

        error_message = d.pop("errorMessage", UNSET)

        error_details = d.pop("errorDetails", UNSET)

        metadata = cls(
            activity_name=activity_name,
            activity_type=activity_type,
            completion_status=completion_status,
            duration_ms=duration_ms,
            error_category=error_category,
            error_type=error_type,
            error_target=error_target,
            error_message=error_message,
            error_details=error_details,
        )

        metadata.additional_properties = d
        return metadata

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
