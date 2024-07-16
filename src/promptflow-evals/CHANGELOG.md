# Release History

## v0.3.2 (Upcoming)

### Features Added
- Introduced `JailbreakAdversarialSimulator` for customers who need to do run jailbreak and non jailbreak adversarial simulations at the same time. More info in the README.md in `/promptflow/evals/synthetic/README.md#jailbreak-simulator`

### Bugs Fixed
- Large simulation was causing a jinja exception, this has been fixed.

### Improvements
- Converted built-in evaluators to async-based implementation, leveraging async batch run for performance improvement.
- Parity between evals and Simulator on signature, passing credentials.
- The `AdversarialSimulator` responds with `category` of harm in the response.

## v0.3.1 (2022-07-09)
- This release contains minor bug fixes and improvements.

<<<<<<< HEAD
## v0.3.0 (2024-05-17)
- Initial release of promptflow-evals package.
=======
- Parity between evals and Simulator on signature, passing credentials.

- Reduced chance of Nan in GPT based evaluators.
- Reduced chance of NaN in GPT based evaluators.

## 0.0.1
- Introduced package
>>>>>>> aeeb53ece (Update src/promptflow-evals/CHANGELOG.md)
