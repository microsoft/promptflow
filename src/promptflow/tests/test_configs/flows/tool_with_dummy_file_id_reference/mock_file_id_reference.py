from promptflow import tool
from promptflow.contracts.multimedia import Image, Text


@tool
def mock_file_id_reference(chat_input: list):
    assert_contain_image_and_text(chat_input)
    chat_output = {
        "content": [
            {"type": "text", "text": "This is a simple text."},
            {"type": "image_file", "image_file": {"file_id": "file-image-001"}},
            {"type": "image_file", "image_file": {"file_id": "file-image-002"}},
            {"type": "text", "text": {
                "value": "This is a complicated text with attached file. [Download the CSV file](sandbox:/mnt/data/dummy.csv)",
                "annotations": [
                    {
                        "type": "file_path",
                        "text": "sandbox:/mnt/data/dummy.csv",
                        "start_index": 67,
                        "end_index":94,
                        "file_path": {
                            "file_id": "file-003"
                        },
                    }
                ]
            }},
        ],
        "file_id_references": {
            "file-image-001": {
                "content": chat_input[1],
                "url": "https://platform.openai.com/files/file-image-001"
            },
            "file-image-002": {
                "content": chat_input[2],
                "url": "https://platform.openai.com/files/file-image-002"
            },
            "file-003": {
                "url" : "https://platform.openai.com/files/file-004"
            }
        }
    }
    return chat_output


def assert_contain_image_and_text(value: any):
    if isinstance(value, list):
        for v in value:
            assert_contain_image_and_text(v)
    elif isinstance(value, dict):
        for _, v in value.items():
            assert_contain_image_and_text(v)
    else:
        assert isinstance(value, (Image, Text))
