from dataclasses import dataclass

import json
import argparse
from pathlib import Path
from pydantic import BaseModel
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from promptflow.contracts.flow import BatchFlowRequest, EvalRequest, NodesRequest  # noqa: E402


@dataclass
class RootObject(BaseModel):
    batch_flow_request: BatchFlowRequest
    eval_request: EvalRequest
    nodes_request: NodesRequest


cur_swagger_folder = Path(__file__).parent / 'v20230330'
cur_swagger_folder.mkdir(exist_ok=True)


def set_definition_to_str(obj):
    obj['type'] = 'string'
    obj.pop("$ref")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output_dir', type=str, default=cur_swagger_folder)
    args = parser.parse_args()
    request_swagger = RootObject.schema()
    request_swagger['swagger'] = '2.0'
    definitions = request_swagger['definitions']
    set_definition_to_str(definitions['Node']['properties']['inputs']['additionalProperties'])
    set_definition_to_str(definitions['FlowOutputDefinition']['properties']['reference'])

    with open(Path(args.output_dir / 'swagger.json'), 'w') as fout:
        json.dump(request_swagger, fout, indent=2)
