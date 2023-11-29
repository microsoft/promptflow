import os


def log(message: str):
    verbose = os.environ.get("VERBOSE", "false")
    if verbose.lower() == "true":
        print(message, flush=True)
