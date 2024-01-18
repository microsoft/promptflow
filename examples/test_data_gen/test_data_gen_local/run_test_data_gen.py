import json
import os
from datetime import datetime

import configargparse
from constants import TEXT_CHUNK
from doc_split import split_doc

from promptflow import PFClient
from promptflow.entities import Run

CONFIG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "config.ini"))


def batch_run_flow(
    pf: PFClient,
    flow_folder: str,
    flow_input_data: str,
    flow_batch_run_size: int,
    connection_name: str = "azure_open_ai_connection",
):
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
        connections={
            "validate_and_generate_seed_question": {"connection": connection_name},
            "validate_and_generate_test_question": {"connection": connection_name},
            "validate_and_generate_context": {"connection": connection_name},
            "generate_answer": {"connection": connection_name},
        },
        column_mapping={TEXT_CHUNK: "${data.text_chunk}"},
        debug=True,
    )

    return base_run


def get_batch_run_output(pf: PFClient, base_run: Run):
    print(f"Start to get batch run {base_run} details.")
    # get run output
    details = pf.get_details(base_run)

    # TODO: error handling like if the run failed because of rate limit.

    question = details["outputs.question"].tolist()
    answer = details["outputs.answer"].tolist()
    context = details["outputs.context"].tolist()
    question_type = details["outputs.question_type"].tolist()
    return [
        {"question": q, "answer": a, "context": c, "question_type": qt}
        for q, a, c, qt in zip(question, answer, context, question_type)
    ]


def clean_data_and_save(test_data_set: list, test_data_output_path: str):
    cleaned_data = [test_data for test_data in test_data_set if test_data and all(val for val in test_data.values())]

    jsonl_str = "\n".join(map(json.dumps, cleaned_data))

    cur_time_str = datetime.now().strftime("%b-%d-%Y-%H-%M-%S")
    with open(os.path.join(test_data_output_path, "test-data-" + cur_time_str + ".jsonl"), "wt") as text_file:
        print(f"{jsonl_str}", file=text_file)


if __name__ == "__main__":
    if os.path.isfile(CONFIG_FILE):
        parser = configargparse.ArgParser(default_config_files=[CONFIG_FILE])
    else:
        raise Exception(
            f"'{CONFIG_FILE}' does not exist. "
            + "Please check if you are under the wrong directory or the file is missing."
        )
    parser.add_argument("--should_skip_doc_split", action="store_true", help="Skip doc split or not")
    parser.add_argument("--documents_folder", required=False, type=str, help="Documents folder path")
    parser.add_argument("--document_chunk_size", required=False, type=int, help="Document chunk size, default is 1024")
    parser.add_argument(
        "--document_nodes_output_path", required=False, type=str, help="Document nodes output path, default is ./"
    )
    parser.add_argument("--flow_folder", required=True, type=str, help="Test data generation flow folder path")
    parser.add_argument(
        "--flow_batch_run_size",
        required=False,
        type=int,
        help="Test data generation flow batch run size, default is 16",
    )
    parser.add_argument("--connection_name", required=True, type=str, help="Promptflow connection name")
    parser.add_argument("--test_data_output_path", required=True, type=str, help="Test data output path.")
    args = parser.parse_args()
    if not (args.documents_folder or args.document_nodes_output_path):
        parser.error("Either 'documents_folder' or 'document_nodes_output_path' should be specified.")

    # check_file_path_exists(args.test_data_output_path)
    if not args.should_skip_doc_split:
        split_doc(args.documents_folder, args.document_nodes_output_path, args.document_chunk_size)

    pf = PFClient()
    # TODO: error handling
    batch_run = batch_run_flow(
        pf,
        args.flow_folder,
        args.document_nodes_output_path,
        args.flow_batch_run_size,
        connection_name=args.connection_name,
    )

    test_data_set = get_batch_run_output(pf, batch_run)
    clean_data_and_save(test_data_set, args.test_data_output_path)
