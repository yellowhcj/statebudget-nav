# External use and feedback protocol

Status: a prospective protocol, not a report of completed human use. No participants, quotes, timings or outcomes have been collected under this protocol.

Purpose: identify whether a researcher can obtain an auditable result and adapt the software to a small question without author-directed debugging. This is an informal formative software evaluation, not a representative usability study or proof of scientific impact. One or two users supply case evidence, not a population estimate.

## Participant brief

You are invited to evaluate a research tool, not to endorse a manuscript. Failure and criticism are useful outcomes. Participation is voluntary. You may stop at any point and choose whether your feedback is quoted, attributed, anonymized or kept private. Use public or synthetic task data for this trial.

Record the exact commit/tag, operating system, Python version, dependencies and any assistance from humans or AI tools. An AI-assisted human run should be reported that way. A person merely signing an agent-generated success report is not an independent human evaluation.

## Task A: acquire, run and understand

1. Starting in a new directory/environment, obtain the tagged public repository and follow WALKTHROUGH.md. Record installation problems and every workaround.
2. Run the FourRooms example and restart audit. Save result JSON, trace, commands and error logs. Explain in your own words which memory resource was measured and what a passing audit establishes.
3. Run the custom-grid example. Identify the local sensor boundary and the retained controller state. Note any explanation you could not follow without assistance.

## Task B: small adaptation chosen by the user

Choose a small question relevant to your work, or adapt the supplied grid sensor/controller. Describe the intended change before running it. Keep private world information outside the controller, document source changes, record the payload limit and outputs, and replay the new trace. If the attempt fails, save the failure and explain what blocked it. A seed-only change is reproduction; a controller/adapter change demonstrates a different level of reuse. Neither alone establishes method superiority.

## Evidence to return

Use USER_FEEDBACK_TEMPLATE.md. Keep original logs, source changes and artifacts. Summarize completion, assistance, obstacles and the specific output obtained. Confirm any quote and its attribution with the participant. Do not require positive wording, infer adoption from a one-off trial or imply that prior acquaintance makes a run independent of author assistance. Acquaintances and collaborators should disclose their relationship.

The author should retain raw failures and disclose changes made after feedback. If the software is fixed, distinguish the original attempt from a retest of the new version. Any manuscript account should separate a packaged example, a user-designed adaptation and sustained research adoption.
