# dev13 candidate validation and remaining archive work (2026-11-13)

- [x] Save completed MovingAI measurements before replay; report audit failures separately.
- [x] Action/state mismatch, process exception, real execution error, no-call and source-drift regressions.
- [x] Historical dev12 installed validation passed 74 tests; this does not certify dev13.
- [x] Physical-task identity and sensor context separated; legacy result metadata supported.
- [ ] Complete dev13 installed tests and source/wheel/install identity verification.
- [x] 15 controller/planner/encoding/retention core files unchanged from dev10.
- [x] Current and historical documentation versions distinguished.
- [ ] Create a permanent software archive and add its real DOI after publication.
- [ ] Final manuscript/attachments, authorship and journal submission checks.

The CI matrix is Windows/Ubuntu x Python3.10/3.12; inspect actual jobs for this
release rather than interpreting a configured workflow as a successful run.
Release assets and their hash manifest identify the delivered build:
https://github.com/yellowhcj/statebudget-nav/releases/tag/v0.1.0-dev13
Historical dev7/dev9 scientific studies keep their original versions. Dev11 changes
failure handling and documentation. Dev13 changes task counting, not navigation
algorithms or historical results. This candidate is not a published release until
the corresponding release page and verified assets exist.
No journal submission, DOI or acceptance is implied.
