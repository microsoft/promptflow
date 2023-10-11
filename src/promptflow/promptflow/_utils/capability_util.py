from pathlib import Path

from promptflow._utils.utils import load_json

CAPABILITY_LIST_FILE = Path(__file__).parent / "capability_list.json"


def get_capability_list():
    capability_list = load_json(CAPABILITY_LIST_FILE)
    return capability_list
