# Independent reuse check

This protocol tests whether a person or AI agent who did not develop StateBudget-Nav can obtain it from a clean checkout and use the documented interface without help from the developer.

## What this can establish

- A clean checkout, installation, and passing test suite support installability and documentation clarity.
- Running the included example supports reproducibility of the packaged demonstration. It is not independent evidence for a new scientific result because the example and expected outcome were created by the developers.
- Connecting a controller or task designed independently of this package is stronger evidence of reuse. Record the adaptation needed and whether the core package had to be changed.
- An AI-only exercise is an agent-based usability test. It does not establish human adoption, independent scientific validation, or journal impact.

## Low-prompt AI-agent check

To test whether the repository explains itself, give a fresh AI agent only the public repository URL and this goal. Start it in a new directory with no access to the developer workspace, private notes, or this protocol:

> Independently obtain and use this research software to complete one of its intended navigation tasks. Work out how to install and run it from the repository. Keep an exact record of what you did, what worked, what failed, and any help you needed. Do not change package source just to make the task pass.

Do not send follow-up instructions during the first attempt unless the agent is blocked by a fact the repository cannot provide, such as unavailable network access. Record any such intervention verbatim. After the attempt, inspect its record and outputs against the acceptance checks below. A later, guided attempt can be useful for debugging but is a separate result.

## Acceptance checks and evidence capture

1. Start from a new directory and environment. Record operating system, Python and dependency versions, network availability, commands run, elapsed time, errors, and any developer assistance.
2. Check whether the agent identified the supported Python version and dependencies, installed the package, and ran the package tests without changing its source.
3. Check whether it completed a real navigation episode and audited the resulting trace in a fresh interpreter. Verify the installed package location/version and preserve output hashes.
4. Preserve the agent's unedited notes, terminal transcript, and generated outputs. Report failed attempts and changes as well as success.
5. If testing scientific reuse, ask the tester to bring a controller or task designed independently of this package and state the research question before seeing comparative results. Freeze that configuration before running it.

An AI-only pass is evidence of agent-based usability and reproducibility of the demonstrated workflow. It does not establish human adoption, independent scientific validation, or journal impact. A human researcher later repeating the test is a distinct and stronger usability observation; running a researcher-designed controller or task is stronger evidence of scientific reuse.
