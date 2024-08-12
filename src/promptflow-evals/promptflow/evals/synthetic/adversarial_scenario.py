# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from enum import Enum


class AdversarialScenario(Enum):
    """Adversarial scenario types"""

    ADVERSARIAL_QA = "adv_qa"
    ADVERSARIAL_CONVERSATION = "adv_conversation"
    ADVERSARIAL_SUMMARIZATION = "adv_summarization"
    ADVERSARIAL_SEARCH = "adv_search"
    ADVERSARIAL_REWRITE = "adv_rewrite"
    ADVERSARIAL_CONTENT_GEN_UNGROUNDED = "adv_content_gen_ungrounded"
    ADVERSARIAL_CONTENT_GEN_GROUNDED = "adv_content_gen_grounded"
    ADVERSARIAL_CONTENT_PROTECTED_MATERIAL = (
        "adv_content_protected_material"  # TODO make sure that the underlying values work properly
    )


class _PrivateAdverarialScenario(Enum):
    """Adversarial scenario types that we haven't published, but still want available for internal use"""

    ADVERSARIAL_CONTENT_ELECTION_CRITICAL_INFORMATION = (
        "adv_content_election_critical_information"  # TODO make sure that the underlying values work properly
    )
