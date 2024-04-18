# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import shlex
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

from flask import Response, jsonify, make_response, request

from promptflow._sdk._constants import FlowRunProperties, get_list_view_type
from promptflow._sdk._errors import RunNotFoundError
from promptflow._sdk._service import Namespace, Resource, fields
from promptflow._sdk._service.utils.utils import build_pfs_user_agent, get_client_from_request, make_response_no_content
from promptflow._sdk.entities import Run as RunEntity
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow._utils.yaml_utils import dump_yaml
from promptflow.contracts._run_management import RunMetadata

api = Namespace("Runs", description="Runs Management")

# Define update run request parsing
update_run_parser = api.parser()
update_run_parser.add_argument("display_name", type=str, location="form", required=False)
update_run_parser.add_argument("description", type=str, location="form", required=False)
update_run_parser.add_argument("tags", type=str, location="form", required=False)

# Define visualize request parsing
visualize_parser = api.parser()
visualize_parser.add_argument("html", type=str, location="form", required=False)

# Response model of run operation
dict_field = api.schema_model("RunDict", {"additionalProperties": True, "type": "object"})
list_field = api.schema_model("RunList", {"type": "array", "items": {"$ref": "#/definitions/RunDict"}})


@api.route("/")
class RunList(Resource):
    @api.response(code=200, description="Runs", model=list_field)
    @api.doc(description="List all runs")
    def get(self):
        # parse query parameters
        max_results = request.args.get("max_results", default=50, type=int)
        all_results = request.args.get("all_results", default=False, type=bool)
        archived_only = request.args.get("archived_only", default=False, type=bool)
        include_archived = request.args.get("include_archived", default=False, type=bool)
        # align with CLI behavior
        if all_results:
            max_results = None
        list_view_type = get_list_view_type(archived_only=archived_only, include_archived=include_archived)

        runs = get_client_from_request().runs.list(max_results=max_results, list_view_type=list_view_type)
        runs_dict = [run._to_dict() for run in runs]
        return jsonify(runs_dict)


@api.route("/submit")
class RunSubmit(Resource):
    @api.response(code=200, description="Submit run info", model=dict_field)
    @api.doc(body=dict_field, description="Submit run")
    def post(self):
        run_dict = request.get_json(force=True)
        run_name = run_dict.get("name", None)
        if not run_name:
            run = RunEntity(**run_dict)
            run_name = run._generate_run_name()
            run_dict["name"] = run_name
        with tempfile.TemporaryDirectory() as temp_dir:
            run_file = Path(temp_dir) / "batch_run.yaml"
            with open(run_file, "w", encoding="utf-8") as f:
                dump_yaml(run_dict, f)
            cmd = [
                "pf",
                "run",
                "create",
                "--file",
                str(run_file),
                "--user-agent",
                build_pfs_user_agent(),
            ]

            if sys.executable.endswith("pfcli.exe"):
                cmd = ["pfcli"] + cmd
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
            stdout, _ = process.communicate()
            if process.returncode == 0:
                try:
                    run = get_client_from_request().runs._get(name=run_name)
                    return jsonify(run._to_dict())
                except RunNotFoundError as e:
                    raise RunNotFoundError(
                        f"Failed to get the submitted run: {e}\n"
                        f"Used command: {' '.join(shlex.quote(arg) for arg in cmd)}\n"
                        f"Output: {stdout.decode('utf-8')}"
                    )
            else:
                raise Exception(f"Create batch run failed: {stdout.decode('utf-8')}")


@api.route("/<string:name>")
class Run(Resource):
    @api.response(code=200, description="Update run info", model=dict_field)
    @api.doc(parser=update_run_parser, description="Update run")
    def put(self, name: str):
        args = update_run_parser.parse_args()
        tags = json.loads(args.tags) if args.tags else None
        run = get_client_from_request().runs.update(
            name=name, display_name=args.display_name, description=args.description, tags=tags
        )
        return jsonify(run._to_dict())

    @api.response(code=200, description="Get run info", model=dict_field)
    @api.doc(description="Get run")
    def get(self, name: str):
        run = get_client_from_request().runs.get(name=name)
        return jsonify(run._to_dict())

    @api.response(code=204, description="Delete run", model=dict_field)
    @api.doc(description="Delete run")
    def delete(self, name: str):
        get_client_from_request().runs.delete(name=name)
        return make_response_no_content()


@api.route("/<string:name>/childRuns")
class FlowChildRuns(Resource):
    @api.response(code=200, description="Child runs", model=list_field)
    @api.doc(description="Get child runs")
    def get(self, name: str):
        run = get_client_from_request().runs.get(name=name)
        local_storage_op = LocalStorageOperations(run=run)
        detail_dict = local_storage_op.load_detail()
        return jsonify(detail_dict["flow_runs"])


@api.route("/<string:name>/nodeRuns/<string:node_name>")
class FlowNodeRuns(Resource):
    @api.response(code=200, description="Node runs", model=list_field)
    @api.doc(description="Get node runs info")
    def get(self, name: str, node_name: str):
        run = get_client_from_request().runs.get(name=name)
        local_storage_op = LocalStorageOperations(run=run)
        detail_dict = local_storage_op.load_detail()
        node_runs = [item for item in detail_dict["node_runs"] if item["node"] == node_name]
        return jsonify(node_runs)


@api.route("/<string:name>/metaData")
class MetaData(Resource):
    @api.doc(description="Get metadata of run")
    @api.response(code=200, description="Run metadata", model=dict_field)
    def get(self, name: str):
        run = get_client_from_request().runs.get(name=name)
        local_storage_op = LocalStorageOperations(run=run)
        metadata = RunMetadata(
            name=run.name,
            display_name=run.display_name,
            create_time=run.created_on,
            flow_path=run.properties[FlowRunProperties.FLOW_PATH],
            output_path=run.properties[FlowRunProperties.OUTPUT_PATH],
            tags=run.tags,
            lineage=run.run,
            metrics=local_storage_op.load_metrics(),
            dag=local_storage_op.load_dag_as_string(),
            flow_tools_json=local_storage_op.load_flow_tools_json(),
        )
        return jsonify(asdict(metadata))


@api.route("/<string:name>/logContent")
class LogContent(Resource):
    @api.doc(description="Get run log content")
    @api.response(code=200, description="Log content", model=fields.String)
    def get(self, name: str):
        run = get_client_from_request().runs.get(name=name)
        local_storage_op = LocalStorageOperations(run=run)
        log_content = local_storage_op.logger.get_logs()
        return make_response(log_content)


@api.route("/<string:name>/metrics")
class Metrics(Resource):
    @api.doc(description="Get run metrics")
    @api.response(code=200, description="Run metrics", model=dict_field)
    def get(self, name: str):
        run = get_client_from_request().runs.get(name=name)
        local_storage_op = LocalStorageOperations(run=run)
        try:
            metrics = local_storage_op.load_metrics()
            return jsonify(metrics)
        except Exception as e:
            api.logger.warning(f"Get {name} metrics failed with {e}")
            return jsonify({})


@api.route("/<string:name>/visualize")
class VisualizeRun(Resource):
    @api.doc(description="Visualize run")
    @api.response(code=200, description="Visualize run", model=fields.String)
    @api.produces(["text/html"])
    def get(self, name: str):
        with tempfile.TemporaryDirectory() as temp_dir:
            from promptflow._sdk.operations import RunOperations

            run_op: RunOperations = get_client_from_request().runs
            html_path = Path(temp_dir) / "visualize_run.html"
            # visualize operation may accept name in string
            run_op.visualize(name, html_path=html_path)

            with open(html_path, "r") as f:
                return Response(f.read(), mimetype="text/html")


@api.route("/<string:name>/archive")
class ArchiveRun(Resource):
    @api.doc(description="Archive run")
    @api.response(code=200, description="Archived run", model=dict_field)
    def get(self, name: str):
        run = get_client_from_request().runs.archive(name=name)
        return jsonify(run._to_dict())


@api.route("/<string:name>/restore")
class RestoreRun(Resource):
    @api.doc(description="Restore run")
    @api.response(code=200, description="Restored run", model=dict_field)
    def get(self, name: str):
        run = get_client_from_request().runs.restore(name=name)
        return jsonify(run._to_dict())
