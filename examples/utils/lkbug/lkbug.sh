#!/bin/bash

# Usage: ./script.sh <command> [<output_file>]

command_to_run=$1

# Check if output file was provided; otherwise use a timestamp-based filename
if [ -z "$2" ]; then
  output_file="output_$(date +%s).txt"
else
  output_file=$2
fi

echo "${command_to_run}" > ${output_file}
# Execute the command and redirect its output to the file
${command_to_run} >> ${output_file} 2>&1

# generate a file named data.jsonl , the content is a jsonl format data of {"log_path": "xxx"}, the xxx should be the output_file
echo "{\"log_path\": \"${output_file}\"}" > data.jsonl

# execute a command "pf run create --flow . --data data.jsonl --type batch" , read the output of the data, there should be a line with name "output_path", find the value of output_path
#flow_command="pf run create --flow . --data data.jsonl --type batch"
#${flow_command}
flow_output=$(pf run create --flow . --data data.jsonl --type batch)

#echo "$flow_output"
# Find the line with the key "output_path" and retrieve its value
output_line=$(echo "$flow_output" | grep "output_path" -m 1)

output_dir=$(echo "$output_line" | awk -F': ' '{print $2}'| sed 's/,$//' | sed 's/"//g')


output_data="${output_dir}\\outputs.jsonl"
#echo "$output_data"

suggest_title=$(python ./parse_output.py ${output_data} | tr -d "\"\'\r\n")
# Output the value of "suggest_title"
echo "$suggest_title"

username=$(az account show --query 'user.name')

description=$(cat "$output_file" | tr -d "\"\'")

#fetch package version information
pip_list_output=$(pip list)
pakcage_info=$(echo "$pip_list_output" | grep "prompt")
#echo "package information"
#echo "$pakcage_info"

#fetch OS Info
if [[ "$OSTYPE" == "linux-gnu" ]]; then
    OSType="Linux"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
    OSType="Windows"
else
    OSType="Unknown"
fi

#echo "OS Information: $OSType"

SystemInfo="package information: $pakcage_info \r\n OS Information: $OSType"
#echo "$SystemInfo"

#echo "$description"

item_cmd="az boards work-item create --title '$suggest_title' --type Bug --assigned-to $username --area 'Vienna\\Pipelines\\SDK' --iteration 'Vienna\\Gallium' --discussion '$description' --fields Microsoft.VSTS.TCM.SystemInfo='$SystemInfo' Microsoft.VSTS.TCM.ReproSteps='$command_to_run'"

eval "$item_cmd"

#echo "$item_cmd"
