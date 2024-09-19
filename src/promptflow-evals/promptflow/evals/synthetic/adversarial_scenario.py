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
    ADVERSARIAL_CONTENT_PROTECTED_MATERIAL = "adv_content_protected_material"
    ADVERSARIAL_INDIRECT_JAILBREAK = "adv_xpia"


class _UnstableAdversarialScenario(Enum):
    """Adversarial scenario types that we haven't published, but still want available for internal use
    Values listed here are subject to potential change, and/or migration to the main enum over time.
    """

    ECI = "adv_politics"
