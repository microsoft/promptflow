import json
import sys

# Get the file path from command-line arguments
file_path = sys.argv[1]

# Read the JSON file
with open(file_path) as json_file:
    data = json.load(json_file)

# Extract the value of "suggest_title"
suggest_title = data["suggest_title"].replace("\"", "")

# Output the value of "suggest_title"
print(suggest_title)
