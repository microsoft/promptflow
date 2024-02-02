DOCUMENT_NODE = "document_node"
TEXT_CHUNK = "text_chunk"

ENVIRONMENT_DICT_FIXED_VERSION = dict(
    image="mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu20.04",
    conda_file={
        "name": "test_data_gen_conda_env",
        "channels": ["defaults"],
        "dependencies": [
            "python=3.10.12",
            "pip=23.2.1",
            {"pip": ["mldesigner==0.1.0b17", "llama_index", "docx2txt", "promptflow"]},
        ],
    },
)
