import os
import subprocess
import multiprocessing
import importlib

git_base = subprocess.check_output(['git', 'rev-parse', '--show-toplevel']).decode().strip()


def walk_and_ignore_pycache(directory):
    list = []
    for root, dirnames, files in os.walk(directory, topdown=True):
        # This line removes any __pycache__ directories from the list
        dirnames[:] = [d for d in dirnames if d != '__pycache__' and d != 'tests' and d != 'data']
        filenames = [f for f in files if f.endswith('.py') and not f.startswith('__init__')]
        for filename in filenames:
            # Process files as you would like
            list.append(os.path.join(root, filename))
    return list


def file_to_import(file):
    push_file = []
    head_tail = os.path.split(file)
    while head_tail[1] != "promptflow" and head_tail[0] != "":
        if head_tail[1].endswith(".py"):
            push_file.insert(0, head_tail[1][:-3])
        else:
            push_file.insert(0, head_tail[1])
        file = head_tail[0]
        head_tail = os.path.split(file)
    push_file.insert(0, "promptflow")
    return ".".join(push_file)


# If there is an import error, the process will exit with a non-zero exit code
# Find this importlib.import_module as the keyword to search for the error
# The error below this is the import error / circular import error.
def subprocess_check_python_import(file):
    print(f'Checking import of {file} on process ID: {os.getpid()}')
    importlib.import_module(file)


def process_file(file):
    import_name = file_to_import(file)
    subprocess_check_python_import(import_name)


if __name__ == '__main__':
    pool = multiprocessing.Pool()
    list = walk_and_ignore_pycache(git_base + "/src/promptflow-tracing/")
    list.extend(walk_and_ignore_pycache(git_base + "/src/promptflow-core/"))
    list.extend(walk_and_ignore_pycache(git_base + "/src/promptflow-devkit/"))
    list.extend(walk_and_ignore_pycache(git_base + "/src/promptflow-azure/"))
    pool.map(process_file, list)
    pool.close()
    pool.join()
