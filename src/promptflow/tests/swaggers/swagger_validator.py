import jsonschema
import json
import argparse
from pathlib import Path


if __name__ == '__main__':
    cur_swagger_dir = Path(__file__).parent / 'v20230330'
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', type=str, default=cur_swagger_dir / 'batch.json')
    parser.add_argument('--eval', type=str, default=cur_swagger_dir / 'eval.json')
    parser.add_argument('--swagger', type=str, default=cur_swagger_dir / 'swagger.json')
    args = parser.parse_args()
    with open(args.batch, "r") as fbatch, open(args.eval, "r") as feval:
        batch_flow_request = json.load(fbatch)
        eval_request = json.load(feval)
        request = {
            "batch_flow_request": batch_flow_request,
            "eval_request": eval_request,
            "nodes_request": batch_flow_request,
        }
    with open(args.swagger, "r") as f:
        swagger = json.load(f)
    jsonschema.validate(request, swagger)
