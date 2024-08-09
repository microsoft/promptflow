from pathlib import Path
import pandas as pd
import mlflow
import argparse
import datetime
from functools import reduce


def parse_args():
    # setup argparse
    parser = argparse.ArgumentParser()

    # add arguments
    parser.add_argument(
        "--eval_qna_rag_metrics_output_folder",
        type=str,
        help="path containing data for qna rag evaluation metrics",
    )
    parser.add_argument(
        "--eval_perceived_intelligence_output_folder",
        type=str,
        default="./",
        help="input path for perceived intelligence evaluation metrics",
    )

    parser.add_argument(
        "--eval_summarization_output_folder",
        type=str,
        default="./",
        help="input path for summarization evaluation metrics",
    )

    parser.add_argument(
        "--eval_results_output",
        type=str,
        default="./",
        help="output path for aggregated metrics",
    )

    # parse args
    args = parser.parse_args()

    # return args
    return args


def get_file(f):
    f = Path(f)
    if f.is_file():
        return f
    else:
        files = list(f.iterdir())
        if len(files) == 1:
            return files[0]
        else:
            raise Exception("********This path contains more than one file*******")


def convert_to_parquet(
    eval_qna_rag_metrics_output_folder,
    eval_perceived_intelligence_output_folder,
    eval_summarization_output_folder,
    eval_results_output,
):
    now = f"{datetime.datetime.now():%Y%m%d%H%M%S}"

    eval_qna_rag_metrics_file = get_file(eval_qna_rag_metrics_output_folder)
    eval_qna_rag_metrics_data = pd.read_json(eval_qna_rag_metrics_file, lines=True)

    eval_perceived_intelligence_file = get_file(
        eval_perceived_intelligence_output_folder
    )
    eval_perceived_intelligence_data = pd.read_json(
        eval_perceived_intelligence_file, lines=True
    )

    eval_summarization_file = get_file(eval_summarization_output_folder)
    eval_summarization_data = pd.read_json(eval_summarization_file, lines=True)

    all_dataframes = [
        eval_qna_rag_metrics_data,
        eval_perceived_intelligence_data,
        eval_summarization_data,
    ]
    eval_results_data = reduce(
        lambda left, right: pd.merge(left, right, on="line_number"), all_dataframes
    )

    eval_results_data["timestamp"] = pd.Timestamp("now")

    eval_results_data.to_parquet(eval_results_output + f"/{now}_eval_results.parquet")

    eval_results_data_mean = eval_results_data.mean(numeric_only=True)

    for metric, avg in eval_results_data_mean.items():
        if metric == "line_number":
            continue
        mlflow.log_metric(metric, avg)


def main(args):
    convert_to_parquet(
        args.eval_qna_rag_metrics_output_folder,
        args.eval_perceived_intelligence_output_folder,
        args.eval_summarization_output_folder,
        args.eval_results_output,
    )


# run script
if __name__ == "__main__":
    # parse args
    args = parse_args()

    # call main function
    main(args)
