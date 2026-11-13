# Changelog

## 0.1.0.dev13 (2026-11-13)

- Separate MovingAI physical map/endpoint/initial-pose identity from sensor context.
- Count a physical task once across different views while still rejecting cross-context trace pairing.
- Derive canonical identity from complete legacy result metadata without rewriting historical files.
- Preserve original sensor-inclusive digest separately in new results and report distinct task/context counts.
- Controller, planner, encoding, retention and zero-call replay semantics are unchanged.

## 0.1.0.dev12 (2026-11-13)

- Enforce LF source checkout bytes with .gitattributes and normalize runtime source before packaging.
- Make Git blobs, source ZIP, wheel and installed runtime files byte-identical.
- Preserve dev11 audit-failure handling and all historical packages and results.

## 0.1.0.dev11 (2026-11-13)

- Save completed MovingAI measurements before replay and preserve them on replay mismatch/process failure.
- Classify completed-run replay failures as study audit errors, excluded from audited success curves.
- Report replay status explicitly, including tasks with no decisions.
- Align current and historical documentation/version scope without moving published tags.
- Controller, planner, encoding and retention algorithms are unchanged.

## 0.1.0.dev10 (2026-11-13)

- Normalize runtime source keys to POSIX paths on Windows and Linux.
- Accept legacy separators without weakening version, source, dependency or plugin checks.
- Reject ambiguous identity paths; clarify original scenario line numbers.
- Preserve earlier studies and require their exact matching software for replay.
- Controller, planner, encoding and retention logic are unchanged.

## 0.1.0.dev9 — study candidate

- Add configurable MiniGrid/MovingAI budget plans composed from existing evaluators.
- Preserve structural infeasibility, runtime/audit errors and incomplete conditions separately.
- Report per-condition budget curves and paired trace divergence with observation-history scope.
- Record portable source/input identities and support relocated reporting and sampled restart replay.
- Controller algorithms and previously frozen scientific results are unchanged.


## 0.1.0.dev8 (unpublished candidate, 2026-11-12)

- Validates bundled controller configuration before reserving trace output.
- Stages and validates MovingAI downloads before publishing the final destination.
- Documents budget sensitivity, complete auxiliary-state accounting and retry behavior.
- Adds a portable two-path research workflow, provenance receipts and direct-tool comparisons.
- Aligns candidate citation/release metadata; historical dev7 evidence remains versioned.
- No controller, map representation, planning or eviction algorithm is changed.

## 0.1.0.dev7 (2026-11-04)

- Full-map CLI accepts trusted external controllers with explicit charged initial bytes.
- Initial payload and external entry-module source are archived before execution.
- A separate installable sparse-map example exercises representation-independent reuse.
- Non-numeric controller diagnostics are excluded from numeric totals; checkpoints preserve decision inputs and output digests.
- Includes the separate optional example, install instructions, and a Windows/Ubuntu CI matrix.
- Historical dev6 scientific evidence and public dev5 identity remain distinct.
- This release integrates tooling; it introduces no new navigation algorithm.

## 0.1.0.dev6 (local candidate)

- Added32-bit coordinates for trusted importable plugins; bundled16-bit policies retain their existing bounds.
- Added a MovingAI map/scenario adapter, original-row selection, local-observation evaluation and task identities.
- Added conventional raster LRU, obstacle-prioritized and face-routing examples with charged32-bit metadata.
- Added a Python search backend and optional portable C++ source/build command.
- Added gzip checkpoint replay and an executable full-map walkthrough.
- This candidate has not yet been pushed or published; it does not create official benchmark scores.

## 0.1.0.dev5

- Added a runnable custom-grid sensor adapter and a four-byte local-walk plugin.
- Added an end-to-end walkthrough and a protocol for collecting actual external feedback.
- Added integration coverage for custom sensor visibility and fresh-interpreter plugin replay.
- Preserved the bundled controller core; no navigation algorithm novelty is claimed.

## 0.1.0.dev4

- Added the MIT license and publication metadata.
- Documented the clean virtual-environment build prerequisites.
- Recorded the public GitHub repository and low-prompt reuse protocol.
- Added final single-author contact and affiliation metadata for the release candidate.

## 0.1.0.dev3

- Added the MIT license, citation/release files and clean-environment build prerequisites.
- Recorded the public repository and low-prompt reuse protocol.

## 0.1.0.dev2

- Added byte-accounted symbolic navigation controllers, restart audits,
  frozen-source batch execution, and packaged research examples.
- Added integration tests and provenance manifests for the bundled controllers.
