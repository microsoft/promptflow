# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license.

import os
import pandas as pd
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--input_data_file", type=str)
parser.add_argument("--output_data_folder", type=str)

args, _ = parser.parse_known_args()

input_df = pd.read_json(args.input_data_file, lines=True)

# data preparation, e.g. data sampling, data cleaning, etc.
processed_data = input_df.sample(n=20, replace=True, random_state=1)

# export data into output folder
output_file_path = os.path.join(args.output_data_folder, "processed_data.csv")
processed_data.to_csv(output_file_path, index=False, header=True)
