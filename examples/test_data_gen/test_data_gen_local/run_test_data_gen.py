from datetime import datetime

import configargparse

from promptflow import PFClient
from promptflow.entities import Run


def batch_run_flow(pf: PFClient, flow_folder: str, flow_input_data: str, flow_batch_run_size: int):
    environment_variables = {
        "PF_WORKER_COUNT": str(flow_batch_run_size),
        "PF_BATCH_METHOD": "spawn",
    }  # TODO: what does 'spawn' mean?

    print("start to run batch flow run.")
    # create run
    base_run = pf.run(
        flow=flow_folder,
        data=flow_input_data,
        stream=True,  # TODO: understand 'stream'
        environment_variables=environment_variables,
        column_mapping={"document_node": "${data.document_node}"},
        debug=True,
    )

    return base_run


def get_batch_run_output(pf: PFClient, base_run: Run):
    print("start to get batch flow run details.")
    # get run output
    details = pf.get_details(base_run)

    return details.output


if __name__ == "__main__":
    parser = configargparse.ArgParser(default_config_files=["./config.ini"])
    parser.add("--documents_folder", required=True, help="Documents folder path")
    parser.add("--document_chunk_size", required=False, help="Document chunk size, default is 1024")
    parser.add("--document_nodes_output_path", required=False, help="Document nodes output path, default is ./")
    parser.add("--flow_folder", required=True, help="Test data generation flow folder path")
    parser.add("--flow_batch_run_size", required=False, help="Test data generation flow batch run size, default is 16")
    args = parser.parse_args()

    pf = PFClient()
    # TODO: error handling
    print(
        f"yao-debug: flow_folder: {args.flow_folder}, document_nodes_output_path: {args.document_nodes_output_path}",
        f"flow_batch_run_size: {args.flow_batch_run_size}\n",
    )
    print(f"batch run start time: {datetime.now()}")
    batch_run = batch_run_flow(pf, args.flow_folder, args.document_nodes_output_path, args.flow_batch_run_size)
    print(f"batch run end time: {datetime.now()}")
    test_data_set = pf.get_details(batch_run)
    print(test_data_set)
