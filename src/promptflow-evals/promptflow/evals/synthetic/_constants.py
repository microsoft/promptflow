# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


class SupportedLanguages:
    """Supported languages for evaluation, using ISO standard language codes.

    Example usage:
        from promptflow.evals.synthetic import AdversarialScenario,
        AdversarialSimulator, SupportedLanguages

        outputs = await simulator(
            target=callback,
            scenario=AdversarialScenario.ADVERSARIAL_CONVERSATION,
            max_simulation_results=5,
            max_conversation_turns=3,
            language=SupportedLanguages.French,
        )
    """

    Spanish = "es"
    Italian = "it"
    French = "fr"
    German = "de"
    SimplifiedChinese = "zh-cn"
    Portuguese = "pt"
    Japanese = "ja"
    English = "en"
