# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license.

import os
import pandas as pd
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--source_data", type=str)
parser.add_argument("--pf_output_data", type=str)
parser.add_argument("--merged_data", type=str)

args, _ = parser.parse_known_args()

source_data_path = os.path.join(args.source_data, "processed_data.csv")
pf_output_path = os.path.join(args.pf_output_data, "parallel_run_step.jsonl")
merged_data_path = os.path.join(args.merged_data, "merged_data.jsonl")

source_data_df = pd.read_csv(source_data_path)
pf_output_df = pd.read_json(pf_output_path, lines=True)

if len(source_data_df) != len(pf_output_df):
    raise Exception("Index mismatch between data source and pf result")

merged_data_df = source_data_df.merge(pf_output_df, how='left', left_index=True, right_on="line_number", suffixes=('', '_predict'))

with open(merged_data_path, "w") as file:
    file.write(merged_data_df.to_json(orient="records", lines=True))
