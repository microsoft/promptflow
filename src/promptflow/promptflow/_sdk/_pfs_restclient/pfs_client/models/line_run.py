import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Type, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.cumulative_token_count import CumulativeTokenCount
    from ..models.line_run_evaluations import LineRunEvaluations
    from ..models.line_run_inputs import LineRunInputs
    from ..models.line_run_outputs import LineRunOutputs


T = TypeVar("T", bound="LineRun")


@_attrs_define
class LineRun:
    """
    Attributes:
        line_run_id (str):
        trace_id (str):
        root_span_id (str):
        inputs (LineRunInputs):
        outputs (LineRunOutputs):
        start_time (datetime.datetime):
        end_time (datetime.datetime):
        status (str):
        latency (str):
        name (str):
        kind (str):
        cumulative_token_count (Union[Unset, CumulativeTokenCount]):
        evaluations (Union[Unset, LineRunEvaluations]):
    """

    line_run_id: str
    trace_id: str
    root_span_id: str
    inputs: "LineRunInputs"
    outputs: "LineRunOutputs"
    start_time: datetime.datetime
    end_time: datetime.datetime
    status: str
    latency: str
    name: str
    kind: str
    cumulative_token_count: Union[Unset, "CumulativeTokenCount"] = UNSET
    evaluations: Union[Unset, "LineRunEvaluations"] = UNSET
    additional_properties: Dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        line_run_id = self.line_run_id

        trace_id = self.trace_id

        root_span_id = self.root_span_id

        inputs = self.inputs.to_dict()

        outputs = self.outputs.to_dict()

        start_time = self.start_time.isoformat()

        end_time = self.end_time.isoformat()

        status = self.status

        latency = self.latency

        name = self.name

        kind = self.kind

        cumulative_token_count: Union[Unset, Dict[str, Any]] = UNSET
        if not isinstance(self.cumulative_token_count, Unset):
            cumulative_token_count = self.cumulative_token_count.to_dict()

        evaluations: Union[Unset, Dict[str, Any]] = UNSET
        if not isinstance(self.evaluations, Unset):
            evaluations = self.evaluations.to_dict()

        field_dict: Dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "line_run_id": line_run_id,
                "trace_id": trace_id,
                "root_span_id": root_span_id,
                "inputs": inputs,
                "outputs": outputs,
                "start_time": start_time,
                "end_time": end_time,
                "status": status,
                "latency": latency,
                "name": name,
                "kind": kind,
            }
        )
        if cumulative_token_count is not UNSET:
            field_dict["cumulative_token_count"] = cumulative_token_count
        if evaluations is not UNSET:
            field_dict["evaluations"] = evaluations

        return field_dict

    @classmethod
    def from_dict(cls: Type[T], src_dict: Dict[str, Any]) -> T:
        from ..models.cumulative_token_count import CumulativeTokenCount
        from ..models.line_run_evaluations import LineRunEvaluations
        from ..models.line_run_inputs import LineRunInputs
        from ..models.line_run_outputs import LineRunOutputs

        d = src_dict.copy()
        line_run_id = d.pop("line_run_id")

        trace_id = d.pop("trace_id")

        root_span_id = d.pop("root_span_id")

        inputs = LineRunInputs.from_dict(d.pop("inputs"))

        outputs = LineRunOutputs.from_dict(d.pop("outputs"))

        start_time = isoparse(d.pop("start_time"))

        end_time = isoparse(d.pop("end_time"))

        status = d.pop("status")

        latency = d.pop("latency")

        name = d.pop("name")

        kind = d.pop("kind")

        _cumulative_token_count = d.pop("cumulative_token_count", UNSET)
        cumulative_token_count: Union[Unset, CumulativeTokenCount]
        if isinstance(_cumulative_token_count, Unset):
            cumulative_token_count = UNSET
        else:
            cumulative_token_count = CumulativeTokenCount.from_dict(
                _cumulative_token_count
            )

        _evaluations = d.pop("evaluations", UNSET)
        evaluations: Union[Unset, LineRunEvaluations]
        if isinstance(_evaluations, Unset):
            evaluations = UNSET
        else:
            evaluations = LineRunEvaluations.from_dict(_evaluations)

        line_run = cls(
            line_run_id=line_run_id,
            trace_id=trace_id,
            root_span_id=root_span_id,
            inputs=inputs,
            outputs=outputs,
            start_time=start_time,
            end_time=end_time,
            status=status,
            latency=latency,
            name=name,
            kind=kind,
            cumulative_token_count=cumulative_token_count,
            evaluations=evaluations,
        )

        line_run.additional_properties = d
        return line_run

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
