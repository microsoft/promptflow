# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

CONVERSATION_PATH = "user.md"
SUMMARIZATION_PATH = "summarization.md"
SEARCH_PATH = "search.md"

CONVERSATION = "conversation"
SUMMARIZATION = "summarization"
SEARCH = "search"

CONTEXT_KEY = {"conversation": ["metadata"], "summarization": ["file_content"], "search": []}


ALL_TEMPLATES = {"conversation": CONVERSATION_PATH, "summarization": SUMMARIZATION_PATH, "search": SEARCH_PATH}

CH_TEMPLATES_COLLECTION_KEY = set(
    [
        "adv_qa",
        "adv_conversation",
        "adv_summarization",
        "adv_search",
        "adv_rewrite",
        "adv_content_gen_ungrounded",
        "adv_content_gen_grounded",
    ]
)
