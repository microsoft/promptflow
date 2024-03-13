from typing import Any, Dict, List, Type, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="CumulativeTokenCount")


@_attrs_define
class CumulativeTokenCount:
    """
    Attributes:
        completion (Union[Unset, int]):
        prompt (Union[Unset, int]):
        total (Union[Unset, int]):
    """

    completion: Union[Unset, int] = UNSET
    prompt: Union[Unset, int] = UNSET
    total: Union[Unset, int] = UNSET
    additional_properties: Dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        completion = self.completion

        prompt = self.prompt

        total = self.total

        field_dict: Dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if completion is not UNSET:
            field_dict["completion"] = completion
        if prompt is not UNSET:
            field_dict["prompt"] = prompt
        if total is not UNSET:
            field_dict["total"] = total

        return field_dict

    @classmethod
    def from_dict(cls: Type[T], src_dict: Dict[str, Any]) -> T:
        d = src_dict.copy()
        completion = d.pop("completion", UNSET)

        prompt = d.pop("prompt", UNSET)

        total = d.pop("total", UNSET)

        cumulative_token_count = cls(
            completion=completion,
            prompt=prompt,
            total=total,
        )

        cumulative_token_count.additional_properties = d
        return cumulative_token_count

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
