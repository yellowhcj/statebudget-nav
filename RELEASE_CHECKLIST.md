# Release verification procedure

For dev14, inspect its actual release assets and CI jobs:
https://github.com/yellowhcj/statebudget-nav/releases/tag/v0.1.0-dev14

1. Test the installed wheel, including wrong trace/result pairing, legacy no-hash
   analysis, completed-outcome audit failure and physical-task/context identity.
2. Verify exact runtime bytes across Git source, source ZIP, wheel and installation.
3. Run a small two-adapter study, relocate its files and replay recorded samples.
4. Inspect actual Windows/Ubuntu x Python 3.10/3.12 jobs for this commit; a configured
   workflow alone is not a successful run. Download the assets and compare hashes.
5. Preserve historical scientific versions and the 15 controller/planner/codec/
   retention core files. A successor is not an exact-source replay replacement.

Historical dev13 passed 81 installed tests; that count does not certify dev14.
Dev14 adds trace/result binding metadata and validation, not a navigation change.
Its current guides distinguish incomplete execution from completed measurements
with replay-audit errors. The immutable source tag and assets record delivery.

Remaining archive/submission work is separate: create a permanent software record
and add its real DOI after publication; check final manuscript/attachments,
authorship and current journal rules. A GitHub release implies none of these.
