# Release History

## v0.3.2 (Upcoming)

### Features Added
- Introduced `JailbreakAdversarialSimulator` for customers who need to do run jailbreak and non jailbreak adversarial simulations at the same time. More info in the README.md in `/promptflow/evals/synthetic/README.md#jailbreak-simulator`
- Exposed batch evaluation run timeout via `PF_BATCH_TIMEOUT_SEC` environment variable. This variable can be used to set the timeout for the batch evaluation for each evaluator and target separately only, not the entire API call.
- Added support for the following languages in the simulator:
  - Spanish (`es`)
  - Italian (`it`)
  - French (`fr`)
  - German (`de`)
  - Simplified Chinese (`zh-cn`)
  - Portuguese (`pt`)
  - Japanese (`ja`)
  - English (`en`)
### Bugs Fixed
- Large simulation was causing a jinja exception, this has been fixed.

### Improvements
- Converted built-in evaluators to async-based implementation, leveraging async batch run for performance improvement. Introduced `PF_EVALS_BATCH_USE_ASYNC` environment variable to enable/disable async batch run, with the default set to False.
- Parity between evals and Simulator on signature, passing credentials.
- The `AdversarialSimulator` responds with `category` of harm in the response.
- Reduced chances of NaNs in GPT based evaluators.


## v0.3.1 (2022-07-09)
- This release contains minor bug fixes and improvements.

## v0.3.0 (2024-05-17)
- Initial release of promptflow-evals package.
