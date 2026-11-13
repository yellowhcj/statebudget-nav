# Version archiving

Software version: `0.1.0.dev12`, MIT license.
Release: https://github.com/yellowhcj/statebudget-nav/releases/tag/v0.1.0-dev12
The immutable release tag identifies the source; source ZIP, matching tool/example
wheels and SHA256 manifest are its release assets. Previous dev7/dev9/dev10/dev11
artifacts remain unchanged. Historical scientific studies require their exact
recorded software; a successor is not an exact-source replacement.

Git tags and GitHub releases do not assign a DOI. No Zenodo DOI is claimed here.
For manual archiving, upload the exact release assets to a Zenodo software record
using `.zenodo.json` and the actual source commit. Check metadata and licenses,
publish the record, then add its real version DOI through an additive documentation
commit. Never move a source tag or replace archived assets to add that DOI.

For future automatic archiving, sign in to https://zenodo.org with GitHub and
enable this repository before a new release. Previous releases are not backfilled:
https://help.zenodo.org/docs/github/
A software DOI is separate from a journal article or library retrieval certificate.
