import requests
import os
import re

from utils.lock import acquire_lock
from utils.logging import log
from constants import PDF_DIR


# Download a pdf file from a url and return the path to the file
def download(url: str) -> str:
    path = os.path.join(PDF_DIR, normalize_filename(url) + ".pdf")
    lock_path = path + ".lock"

    with acquire_lock(lock_path):
        if os.path.exists(path):
            log("Pdf already exists in " + os.path.abspath(path))
            return path

        log("Downloading pdf from " + url)
        response = requests.get(url)

        with open(path, "wb") as f:
            f.write(response.content)

        return path


def normalize_filename(filename):
    # Replace any invalid characters with an underscore
    return re.sub(r"[^\w\-_. ]", "_", filename)
