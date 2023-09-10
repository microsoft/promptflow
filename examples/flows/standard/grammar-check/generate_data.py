import os
import json

def find_py_files(directory):

    sql_files = []

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                sql_files.append(os.path.abspath(os.path.join(root, file)))

    return sql_files

def write_to_jsonl(files, output_file="data.jsonl"):
    """
    Write list of file paths to a JSON lines file.
    
    Args:
    - files (list): List of file paths.
    - output_file (str): Name of the output JSON lines file.
    """
    with open(output_file, 'w') as out:
        for file_path in files:
            line = json.dumps({"path": file_path})
            out.write(line + '\n')

if __name__ == "__main__":
    directory = "../../../"
    sql_files = find_py_files(directory)
    write_to_jsonl(sql_files)
    print(f"Output written to data.jsonl")
