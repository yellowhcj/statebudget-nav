# dev7 release preparation (2026-11-04)

The release source includes the complete-map adapter and optional separately
installable external example. A four-job CI matrix is configured; consult its
live result. Publication commit, release assets and remote verification are
recorded in the release receipt, rather than inferred from this checklist.
DOI archiving requires a published Zenodo record; see ARCHIVING.md.

## Historical local preparation records

# Separate dev7 candidate

External full-map plugins, explicit initial bytes and source snapshots are validated in the accompanying S6 review artifact. dev7 has not been pushed or publicly released. Historical dev6/dev5 facts below retain their original meaning.

# Local dev6 candidate status (2026-11-04)

- [x] Original dev5 sources preserved before changes.
- [x]25 current interface/workflow tests;390 frozen pilot checkpoint matches.
- [x]156 Python-backend sample matches and130 public fresh-process checks.
- [x] Installed wheel in isolated venv; declared dependencies downloaded by pip.
- [x] Official map/scenario download command exercised; hashes and attribution saved.
- [x] Python/native full trajectories matched on one official task; legacy MiniGrid CLI checked.
- [ ] Push/tag/release dev6 and replace local candidate identity with a permanent public link.
- [ ] Author/advisor approval, declarations, current journal qualification/guide and submission.

Below records historical dev5 release facts. They do not assert that dev6 has
already been pushed, externally adopted, assigned a DOI or submitted.

# Release checklist

This checklist records release facts without claiming journal acceptance or
school recognition.

- [x] Public GitHub repository: https://github.com/yellowhcj/statebudget-nav
- [x] Main branch is pushed and can be cloned from a separate directory.
- [x] MIT license files included as `LICENSE` and `Licence.txt` for GitHub and publisher-template compatibility.
- [x] Package metadata names the repository and license.
- [x] Changelog and citation metadata included.
- [x] Package tests pass locally (17 tests, including the custom sensor/plugin path).
- [x] Clean wheel, navigation example, and fresh-process audit recorded.
- [x] Independent AI-agent reuse report recorded separately from developer notes.
- [x] Replace the account-name copyright holder with the supplied author name.
- [x] Add the supplied author name, affiliation, and support email.
- [ ] Add DOI archive.
- [ ] Recheck journal indexing and warning-list status at submission.
- [x] dev5 wheel and source distribution built locally; the release candidate includes the custom-grid example.
- [x] Public dev5 tag verified from a separate clone (commit b326eeb66a06a3fdb8e08bc82da244272c02b235): 17 tests pass; custom-grid all-decision replay passes 89/89; source and trace fingerprints preserved. This is author verification with existing dependencies, not independent human reuse.
- [ ] Create a GitHub Release / permanent DOI archive if chosen; a Git tag alone is not DOI archiving.
