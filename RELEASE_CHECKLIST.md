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
