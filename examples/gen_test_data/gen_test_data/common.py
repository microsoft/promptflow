import json
import re
import sys
import time
import typing as t
from pathlib import Path

from constants import DOCUMENT_NODE, NODES_FILE_NAME, SUPPORT_FILE_TYPE, TEXT_CHUNK

from promptflow._utils.logger_utils import get_logger


def split_document(chunk_size, chunk_overlap, documents_folder, document_node_output):
    try:
        from llama_index import SimpleDirectoryReader
        from llama_index.node_parser import SentenceSplitter
        from llama_index.readers.schema import Document as LlamaindexDocument
        from llama_index.schema import BaseNode
    except ImportError as e:
        raise ImportError(
            f"{str(e)}. It appears that `llama_index` may not be installed, or the installed version may be incorrect."
            "Please check `requirements.txt` file and install all the dependencies."
        )

    logger = get_logger("doc.split")
    logger.info("Step 1: Start to split documents to document nodes...")
    # count the number of files in documents_folder, including subfolders.
    all_files = [f for f in Path(documents_folder).rglob("*") if f.is_file()]
    filtered_num_files = sum(1 for _ in all_files if _.suffix.lower() in SUPPORT_FILE_TYPE)
    logger.info(
        f"Found {len(all_files)} files in the documents folder '{documents_folder}'. "
        f"After filtering out unsupported file types, {filtered_num_files} files remain."
        f"Using chunk size: {chunk_size} to split."
    )
    # `SimpleDirectoryReader` by default chunk the documents based on heading tags and paragraphs, which may lead to small chunks.  # noqa: E501
    reader = SimpleDirectoryReader(documents_folder, required_exts=SUPPORT_FILE_TYPE, recursive=True, encoding="utf-8")
    # Disable the default suffixes to avoid splitting the documents into small chunks.
    # TODO: find a better way to disable the default suffixes.
    SimpleDirectoryReader.supported_suffix = []
    chunks = reader.load_data()
    # Convert documents into nodes
    node_parser = SentenceSplitter.from_defaults(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap, include_metadata=True
    )
    chunks = t.cast(t.List[LlamaindexDocument], chunks)
    document_nodes: t.List[BaseNode] = node_parser.get_nodes_from_documents(documents=chunks)
    logger.info(f"Split the documents and created {len(document_nodes)} document nodes.")
    document_nodes_output_path = document_node_output / Path(NODES_FILE_NAME)
    with open(document_nodes_output_path, "wt") as text_file:
        for doc in document_nodes:
            print(json.dumps({TEXT_CHUNK: doc.text, DOCUMENT_NODE: doc.to_json()}), file=text_file)

    logger.info(f"Saved document nodes to '{document_nodes_output_path}'.")
    return str(Path(document_node_output) / NODES_FILE_NAME)


def clean_data(test_data_set: list, test_data_output_path: str):
    logger = get_logger("data.clean")
    logger.info("Step 3: Start to clean invalid test data...")
    logger.info(f"Collected {len(test_data_set)} test data after the batch run.")
    cleaned_data = []

    for test_data in test_data_set:
        if test_data and all(
            val and val != "(Failed)" for key, val in test_data.items() if key.lower() != "line_number"
        ):
            data_line = {"question": test_data["question"], "suggested_answer": test_data["suggested_answer"]}
            cleaned_data.append(data_line)

    jsonl_str = "\n".join(map(json.dumps, cleaned_data))
    with open(test_data_output_path, "wt") as text_file:
        print(f"{jsonl_str}", file=text_file)

    # TODO: aggregate invalid data root cause and count, and log it.
    # log debug info path.
    logger.info(
        f"Removed {len(test_data_set) - len(cleaned_data)} invalid test data. "
        f"Saved {len(cleaned_data)} valid test data to '{test_data_output_path}'."
    )


def count_non_blank_lines(file_path):
    with open(file_path, "r") as file:
        lines = file.readlines()

    non_blank_lines = len([line for line in lines if line.strip()])
    return non_blank_lines


def print_progress(log_file_path: str, process):
    from tqdm import tqdm

    logger = get_logger("data.gen")
    finished_log_pattern = re.compile(r".*execution.bulk\s+INFO\s+Finished (\d+) / (\d+) lines\.")
    progress_log_pattern = re.compile(
        r".*execution.bulk\s+INFO.*\[Finished: (\d+)\] \[Processing: (\d+)\] \[Pending: (\d+)\]"
    )
    # wait for the log file to be created
    start_time = time.time()
    while not Path(log_file_path).is_file():
        time.sleep(1)
        # if the log file is not created within 5 minutes, raise an error
        if time.time() - start_time > 300:
            raise Exception(f"Log file '{log_file_path}' is not created within 5 minutes.")

    logger.info(f"Click '{log_file_path}' to see detailed batch run log. Showing the progress here...")
    progress_bar = None
    try:
        last_data_time = time.time()
        with open(log_file_path, "r") as f:
            while True:
                status = process.poll()
                # status is None if not finished, 0 if finished successfully, and non-zero if failed
                if status:
                    stdout, _ = process.communicate()
                    raise Exception(f"Batch run failed due to {stdout.decode('utf-8')}")

                line = f.readline().strip()
                if line:
                    last_data_time = time.time()  # Update the time when the last data was received
                    progress_match = progress_log_pattern.match(line)
                    finished_match = finished_log_pattern.match(line)
                    if not progress_match and not finished_match:
                        continue

                    if progress_match:
                        finished, processing, pending = map(int, progress_match.groups())
                        total = finished + processing + pending
                        if progress_bar is None:
                            # Set mininterval=0 to refresh the progress bar when it calls progress_bar.update
                            # after initialization.
                            progress_bar = tqdm(total=total, desc="Processing", mininterval=0, file=sys.stdout)
                        progress_bar.update(finished - progress_bar.n)

                    if finished_match:
                        finished, total = map(int, finished_match.groups())
                        if progress_bar is None:
                            progress_bar = tqdm(total=total, desc="Processing", mininterval=0, file=sys.stdout)
                        progress_bar.update(finished - progress_bar.n)

                        if finished == total:
                            progress_bar.close()
                            logger.info("Batch run is completed.")

                            break
                elif time.time() - last_data_time > 300:
                    logger.info(
                        "No new log line received for 5 minutes. Stop reading. "
                        f"See the log file '{log_file_path}' for more details."
                    )
                    break
                else:
                    time.sleep(1)  # wait for 1 second if no new line is available
    except Exception as e:
        raise Exception(f"Error occurred while printing batch run progress: {e}.")
    finally:
        if progress_bar:
            progress_bar.close()


def convert_to_abs_path(file_path: str) -> str:
    if not file_path:
        return file_path

    path = Path(file_path)
    if path.is_absolute():
        return str(path)
    elif path.exists():
        abs = str(path.resolve())
        return abs
    else:
        return file_path


def local_path_exists(path):
    return Path(path).exists()


def non_padding_path(path):
    return not (path.startswith("<") and path.endswith(">"))


def _retrieve_file_names_from_document_nodes_file(document_nodes_file_path) -> t.List[str]:
    text_info = {}
    with open(document_nodes_file_path, "r") as file:
        for line in file:
            # Should skip empty new lines, otherwise, json.loads would throw error.
            if not line.strip():
                continue
            line_json = json.loads(line)
            text_chunk = line_json[TEXT_CHUNK]
            document_node = json.loads(line_json["document_node"])
            file_path = document_node["metadata"]["file_path"]
            text_info[text_chunk] = file_path
    return text_info


def _count_lines(file_path) -> int:
    with open(file_path, "r") as f:
        return sum(1 for line in f if line.strip())


def summarize_batch_run_res(gen_details_file_path, document_nodes_file_path, output_file_path):
    success_count = 0
    validate_failed_count = 0
    validate_failed_steps = {}
    validate_failed_distribution = {}

    nodes_file_lines_count = _count_lines(document_nodes_file_path)
    document_nodes_info = _retrieve_file_names_from_document_nodes_file(document_nodes_file_path)

    with open(gen_details_file_path, "r") as details_f:
        for details_line in details_f:
            # Should skip empty new lines, otherwise, json.loads would throw error.
            if not details_line.strip():
                continue
            data = json.loads(details_line)
            if data["debug_info"] == "(Failed)":
                continue

            if data["debug_info"]["validation_summary"]["success"]:
                success_count += 1
            else:
                validate_failed_count += 1
                failed_step = data["debug_info"]["validation_summary"]["failed_step"]

                if failed_step in validate_failed_steps:
                    validate_failed_steps[failed_step] += 1
                else:
                    validate_failed_steps[failed_step] = 1
                    validate_failed_distribution[failed_step] = {}

                document_name = document_nodes_info[data["debug_info"]["text_chunk"]]
                if document_name in validate_failed_distribution[failed_step]:
                    validate_failed_distribution[failed_step][document_name] += 1
                else:
                    validate_failed_distribution[failed_step][document_name] = 1

    data = {
        "total_count": nodes_file_lines_count,
        "success_count": success_count,
        "run_failed_count": nodes_file_lines_count - success_count - validate_failed_count,
        "validate_failed_count": validate_failed_count,
        "validate_failed_steps": validate_failed_steps,
        "validate_failed_distribution": validate_failed_distribution,
    }

    with open(output_file_path, "w") as file:
        json.dump(data, file, indent=4)
