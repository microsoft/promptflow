# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license.

import os
import pandas as pd
import argparse
import glob
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("--source_data", type=str)
parser.add_argument("--pf_output_data", type=str)
parser.add_argument("--pf_debug_data", type=str)
parser.add_argument("--merged_data", type=str)

args, _ = parser.parse_known_args()

source_data_path = os.path.join(args.source_data, "processed_data.csv")
pf_output_path = os.path.join(args.pf_output_data, "parallel_run_step.jsonl")
merged_data_path = os.path.join(args.merged_data, "merged_data.jsonl")

if args.pf_debug_data is not None:
    pf_debug_files = glob.glob(os.path.join(args.pf_debug_data, "flow_artifacts/*.jsonl"))

source_data_df = pd.read_csv(source_data_path)
pf_output_df = pd.read_json(pf_output_path, lines=True)
pf_output_df.sort_values(by="line_number", inplace=True, ignore_index=True)

if len(source_data_df) != len(pf_output_df):
    raise Exception("Index mismatch between data source and pf result")

source_data_df.loc[:, "line_number"] = pf_output_df.loc[:, "line_number"]
source_data_df.loc[:, "pred_category"] = pf_output_df.loc[:, "category"]
source_data_df.loc[:, "pred_evidence"] = pf_output_df.loc[:, "evidence"]

if pf_debug_files is not None and len(pf_debug_files) > 0:
    debug_df = pd.concat([pd.read_json(file, lines=True) for file in pf_debug_files])
    debug_df.sort_values(by="line_number", inplace=True, ignore_index=True)
    for i in range(len(debug_df)):
        source_data_df.loc[i, "prompt_tokens"] = debug_df.loc[i, "run_info"]["system_metrics"]["prompt_tokens"]
        source_data_df.loc[i, "duration"] = debug_df.loc[i, "run_info"]["system_metrics"]["duration"]
        source_data_df.loc[i, "completion_tokens"] = debug_df.loc[i, "run_info"]["system_metrics"]["completion_tokens"]
        source_data_df.loc[i, "total_tokens"] = debug_df.loc[i, "run_info"]["system_metrics"]["total_tokens"]
else:
    source_data_df.loc[:, "prompt_tokens"] = np.nan
    source_data_df.loc[:, "duration"] = np.nan
    source_data_df.loc[:, "completion_tokens"] = np.nan
    source_data_df.loc[:, "total_tokens"] = np.nan

with open(merged_data_path, "w") as file:
    file.write(source_data_df.to_json(orient="records", lines=True))
