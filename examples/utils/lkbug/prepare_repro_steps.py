import json
import sys

cmd_output_path = sys.argv[1]
llm_output_path = sys.argv[2]
package_info = sys.argv[3]

with open(cmd_output_path) as f:
    cmd_output = f.read()

with open(llm_output_path) as f:
    llm_output = json.load(f)

result = f"""
SDK/CLI version: 
{package_info}

Suggested fix: 
{llm_output["suggest_fix"]}

Repro steps: 
{cmd_output}
""".replace("\"", "")

print(result)
