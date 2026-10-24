# Independent reuse check

This protocol tests whether a person or AI agent who did not develop StateBudget-Nav can obtain it from a clean checkout and use the documented interface without help from the developer.

## What this can establish

- A clean checkout, installation, and passing test suite support installability and documentation clarity.
- Running the included example supports reproducibility of the packaged demonstration. It is not independent evidence for a new scientific result because the example and expected outcome were created by the developers.
- Connecting a controller or task designed independently of this package is stronger evidence of reuse. Record the adaptation needed and whether the core package had to be changed.
- An AI-only exercise is an agent-based usability test. It does not establish human adoption, independent scientific validation, or journal impact.

## Procedure

1. Give the tester only the public repository URL and a short goal, such as: “Install this package from a clean environment; run one real navigation task; save the result and audit it in a fresh process; report any unclear or failed steps.” Do not provide private notes or step-by-step help during the first attempt.
2. Start from a new directory and environment. Record operating system, Python and dependency versions, network availability, commands run, elapsed time, errors, and any developer assistance.
3. Require the tester to verify the installed package location and version, run the test suite, complete a navigation episode, and replay checkpoints in a fresh interpreter.
4. If testing scientific reuse, ask the tester to bring a controller or task of their own and state the research question before seeing comparative results. Freeze that configuration before running it.
5. Preserve the tester's unedited notes and output hashes. Report failed attempts and changes as well as success. Do not describe an AI-only pass as a human user study or as independent adoption.

## Suggested prompt for a fresh AI agent

> You are evaluating a research software package for independent usability. Use a new directory and do not assume access to its development workspace. From the repository, determine the supported Python version and dependencies, install the package, run its tests, execute one documented navigation task, and audit its trace in a fresh process. Do not modify package source to make the test pass. Save the exact commands, versions, output files, elapsed time, failures, and any assumptions in `reuse_report.md`. Distinguish successful installation and example reproduction from scientific validation or human adoption.

For a stronger test, replace the built-in demonstration with a controller and task of your own, describe the intended question before inspecting results, and record every package change required to run it.
