# promptflow-evals package

Please insert change log into "Next Release" ONLY.

## Next release

## 0.3.2

- Introduced `JailbreakAdversarialSimulator` for customers who need to do run jailbreak and non jailbreak adversarial simulations at the same time. More info [here](./promptflow/evals/synthetic/README.md#jailbreak-simulator)

- The `AdversarialSimulator` responds with `category` of harm in the response.

- Large simulation was causing a jinja exception, this has been fixed

- Parity between evals and Simulator on signature, passing credentials.

## 0.0.1
- Introduced package
