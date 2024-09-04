# Release History

## v0.3.3 (Upcoming)
### Features Added
- Add a new evaluator (ProtectedMaterialsEvaluator) and associated adversarial content simulator enum type (AdversarialScenario.ADVERSARIAL_CONTENT_PROTECTED_MATERIAL) for protected materials, which determines if given inputs contain materials protected by IP laws.
- Introduced `IndirectAttackSimulator` to simulate XPIA (cross domain prompt injected attack) jailbreak attacks on your AI system.
- Introduced `IndirectAttackEvaluator` to evaluate content for the presence of XPIA (cross domain prompt injected attacks) injected into conversation or Q/A context to interrupt normal expected functionality by eliciting manipulated content, intrusion and attempting to gather information outside the scope of your AI system.

### Bugs Fixed
- Fixed evaluators to accept (non-Azure) Open AI Configs.

### Breaking Changes
- Replaced `jailbreak` parameter in `AdversarialSimulator` with `_jailbreak_type` parameter to support multiple jailbreak types. Instead of editing this parameter directly, we recommend using the `JailbreakAdversarialSimulator` class for UPIA jailbreak and `IndirectAttackSimulator` class for XPIA jailbreak.

### Improvements
- Set the PF_EVALS_BATCH_USE_ASYNC environment variable to True by default to enable asynchronous batch run for async-enabled built-in evaluators, improving performance.

## v0.3.2 (2024-08-13)
### Features Added
- Introduced `JailbreakAdversarialSimulator` for customers who need to do run jailbreak and non jailbreak adversarial simulations at the same time. More info in the README.md in `/promptflow/evals/synthetic/README.md#jailbreak-simulator`
- Exposed batch evaluation run timeout via `PF_BATCH_TIMEOUT_SEC` environment variable. This variable can be used to set the timeout for the batch evaluation for each evaluator and target separately only, not the entire API call.

### Bugs Fixed
- Large simulation was causing a jinja exception, this has been fixed.
- Fixed the issue where the relative data path was not working with the evaluate API when using multiple evaluators.

### Improvements
- Converted built-in evaluators to async-based implementation, leveraging async batch run for performance improvement. Introduced `PF_EVALS_BATCH_USE_ASYNC` environment variable to enable/disable async batch run, with the default set to False.
- Parity between evals and Simulator on signature, passing credentials.
- The `AdversarialSimulator` responds with `category` of harm in the response.
- Reduced chances of NaNs in GPT based evaluators.

## v0.3.1 (2024-07-09)
- This release contains minor bug fixes and improvements.

## v0.3.0 (2024-05-17)
- Initial release of promptflow-evals package.
