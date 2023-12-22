# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from marshmallow import fields, post_load

from promptflow._sdk._constants import JobType
from promptflow._sdk.schemas._base import PatchedSchemaMeta, YamlFileSchema
from promptflow._sdk.schemas._fields import LocalPathField, NestedField, StringTransformedEnum, UnionField
from promptflow._sdk.schemas._run import RunSchema


class ToolSourceSchema(metaclass=PatchedSchemaMeta):
    type = StringTransformedEnum(allowed_values=["code", "package"], required=True)
    tool = fields.Str()
    path = LocalPathField()


class AggregationJobSchema(metaclass=PatchedSchemaMeta):
    # TODO: Finalize the schema required fields
    name = fields.Str(required=True)
    type = StringTransformedEnum(allowed_values=JobType.AGGREGATION, required=True)
    source = NestedField(ToolSourceSchema, required=True)
    inputs = fields.Dict(keys=fields.Str)
    # runtime field, only available for cloud run
    runtime = fields.Str()  # TODO: Revisit the required fields
    display_name = fields.Str()
    environment_variables = fields.Dict(keys=fields.Str, values=fields.Str)


class FlowJobSchema(RunSchema):
    name = fields.Str(required=True)
    type = StringTransformedEnum(allowed_values=JobType.FLOW, required=True)


class OrchestrationSchema(YamlFileSchema):
    data = LocalPathField()  # Optional, orchestration can have a data_gen job
    jobs = fields.List(UnionField([NestedField(FlowJobSchema), NestedField(AggregationJobSchema)]), required=True)

    @post_load
    def resolve_jobs(self, data, **kwargs):
        from promptflow._sdk.entities._orchestration import AggregationJob, FlowJob

        jobs = data.get("jobs", [])

        resolved_jobs = []
        for job_instance in jobs:
            if not isinstance(job_instance, dict):
                continue
            job_type = job_instance.get("type", None)
            if job_type == "flow":
                resolved_jobs.append(
                    FlowJob._load_from_dict(data=job_instance, context=self.context, additional_message="")
                )
            elif job_type == "script":
                resolved_jobs.append(
                    AggregationJob._load_from_dict(data=job_instance, context=self.context, additional_message="")
                )
            else:
                raise ValueError(f"Unknown job type {job_type} for job {job_instance}.")
        data["jobs"] = resolved_jobs

        return data
