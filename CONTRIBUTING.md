# Contributing to Prompt Flow
You can contribute to prompt flow with issues and pull requests (PRs). Simply
filing issues for problems you encounter is a great way to contribute. Contributing
code is greatly appreciated.

## Reporting Issues

We always welcome bug reports, API proposals and overall feedback. Here are a few
tips on how you can make reporting your issue as effective as possible.

### Where to Report

New issues can be reported in our [list of issues](https://github.com/microsoft/promptflow/issues).

Before filing a new issue, please search the list of issues to make sure it does
not already exist.

If you do find an existing issue for what you wanted to report, please include
your own feedback in the discussion. Do consider upvoting (👍 reaction) the original
post, as this helps us prioritize popular issues in our backlog.

### Writing a Good Bug Report

Good bug reports make it easier for maintainers to verify and root cause the
underlying problem.
The better a bug report, the faster the problem will be resolved. Ideally, a bug
report should contain the following information:

- A high-level description of the problem.
- A _minimal reproduction_, i.e. the smallest size of code/configuration required
  to reproduce the wrong behavior.
- A description of the _expected behavior_, contrasted with the _actual behavior_ observed.
- Information on the environment: OS/distribution, CPU architecture, SDK version, etc.
- Additional information, e.g. Is it a regression from previous versions? Are there
  any known workarounds?

## Contributing Changes

Project maintainers will merge accepted code changes from contributors.

### DOs and DON'Ts

DO's:

- **DO** follow the standard coding conventions: [Python](https://pypi.org/project/black/)
- **DO** give priority to the current style of the project or file you're changing
  if it diverges from the general guidelines.
- **DO** include tests when adding new features. When fixing bugs, start with
  adding a test that highlights how the current behavior is broken.
- **DO** add proper docstring for functions and classes following [API Documentation Guidelines](./docs/dev/documentation_guidelines.md).
- **DO** keep the discussions focused. When a new or related topic comes up
  it's often better to create new issue than to side track the discussion.
- **DO** clearly state on an issue that you are going to take on implementing it.
- **DO** blog and tweet (or whatever) about your contributions, frequently!

DON'Ts:

- **DON'T** surprise us with big pull requests. Instead, file an issue and start
  a discussion so we can agree on a direction before you invest a large amount of time.
- **DON'T** commit code that you didn't write. If you find code that you think is a good
  fit to add to prompt flow, file an issue and start a discussion before proceeding.
- **DON'T** submit PRs that alter licensing related files or headers. If you believe
  there's a problem with them, file an issue and we'll be happy to discuss it.
- **DON'T** make new APIs without filing an issue and discussing with us first.

### Breaking Changes

Contributions must maintain API signature and behavioral compatibility. Contributions
that include breaking changes will be rejected. Please file an issue to discuss
your idea or change if you believe that a breaking change is warranted.

### Suggested Workflow

We use and recommend the following workflow:

1. Create an issue for your work, or reuse an existing issue on the same topic.
   - Get agreement from the team and the community that your proposed change is
     a good one.
   - Clearly state that you are going to take on implementing it, if that's the case.
     You can request that the issue be assigned to you. Note: The issue filer and
     the implementer don't have to be the same person.
2. Create a personal fork of the repository on GitHub (if you don't already have one).
3. In your fork, create a branch off of main (`git checkout -b my_branch`).
   - Name the branch so that it clearly communicates your intentions, such as
     "issue-123" or "githubhandle-issue".
4. Make and commit your changes to your branch.
5. Add new tests corresponding to your change, if applicable.
6. Run the relevant scripts in [the section below](https://github.com/microsoft/promptflow/blob/main/CONTRIBUTING.md#development-scripts) to ensure that your build is clean and all tests are passing.
7. Create a PR against the repository's **main** branch.
   - State in the description what issue or improvement your change is addressing.
   - Link the PR to the issue in step 1.
   - Verify that all the Continuous Integration checks are passing.
8. Wait for feedback or approval of your changes from the code maintainers.
   - If there is no response for a few days, you can create a new issue to raise awareness.
     Promptflow team has triage process toward issues without assignee,
     then you can directly contact the issue owner to follow up (e.g. loop related internal reviewer).
9. When area owners have signed off, and all checks are green, your PR will be merged.

### Development scripts

The scripts below are used to build, test, and lint within the project.

- see [doc/dev/dev_setup.md](https://github.com/microsoft/promptflow/blob/main/docs/dev/dev_setup.md).


### PR - CI Process

The continuous integration (CI) system will automatically perform the required
builds and run tests (including the ones you are expected to run) for PRs. Builds
and test runs must be clean.

If the CI build fails for any reason, the PR issue will be updated with a link
that can be used to determine the cause of the failure.
