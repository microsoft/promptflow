from typing import Any, Dict, List, Type, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="PostExperimentStartBody")


@_attrs_define
class PostExperimentStartBody:
    """
    Attributes:
        name (Union[Unset, str]):
        template (Union[Unset, str]):
        stream (Union[Unset, bool]):
        from_nodes (Union[Unset, str]):
        nodes (Union[Unset, str]):
        inputs (Union[Unset, str]):
        executable_path (Union[Unset, str]):
    """

    name: Union[Unset, str] = UNSET
    template: Union[Unset, str] = UNSET
    stream: Union[Unset, bool] = UNSET
    from_nodes: Union[Unset, str] = UNSET
    nodes: Union[Unset, str] = UNSET
    inputs: Union[Unset, str] = UNSET
    executable_path: Union[Unset, str] = UNSET
    additional_properties: Dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        name = self.name

        template = self.template

        stream = self.stream

        from_nodes = self.from_nodes

        nodes = self.nodes

        inputs = self.inputs

        executable_path = self.executable_path

        field_dict: Dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if template is not UNSET:
            field_dict["template"] = template
        if stream is not UNSET:
            field_dict["stream"] = stream
        if from_nodes is not UNSET:
            field_dict["from_nodes"] = from_nodes
        if nodes is not UNSET:
            field_dict["nodes"] = nodes
        if inputs is not UNSET:
            field_dict["inputs"] = inputs
        if executable_path is not UNSET:
            field_dict["executable_path"] = executable_path

        return field_dict

    @classmethod
    def from_dict(cls: Type[T], src_dict: Dict[str, Any]) -> T:
        d = src_dict.copy()
        name = d.pop("name", UNSET)

        template = d.pop("template", UNSET)

        stream = d.pop("stream", UNSET)

        from_nodes = d.pop("from_nodes", UNSET)

        nodes = d.pop("nodes", UNSET)

        inputs = d.pop("inputs", UNSET)

        executable_path = d.pop("executable_path", UNSET)

        post_experiment_start_body = cls(
            name=name,
            template=template,
            stream=stream,
            from_nodes=from_nodes,
            nodes=nodes,
            inputs=inputs,
            executable_path=executable_path,
        )

        post_experiment_start_body.additional_properties = d
        return post_experiment_start_body

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
