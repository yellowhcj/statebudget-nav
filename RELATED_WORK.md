# Related tools and the reuse boundary

Updated 2026-11-12. These observations are based on official documentation and
source reading, not third-party-tool performance measurements or a systematic
proof of exclusive capability.

| Existing tool | Relevant established capability | Role of this toolkit |
| --- | --- | --- |
| [MiniGrid](https://github.com/Farama-Foundation/Minigrid), [Gymnasium](https://github.com/Farama-Foundation/Gymnasium) | Modular environments, observations/actions and episode execution | Reuses MiniGrid and supplies a declared controller-byte contract and audit records |
| [POPGym](https://github.com/proroklab/popgym), [Memory Gym](https://github.com/MarcoMeter/endless-memory-gym) | Memory-dependent tasks, explicit memory interfaces and capacity comparisons | Implements a symbolic-state workflow; neither memory evaluation nor matched capacity is new here |
| [Memory Maze](https://github.com/jurgisp/memory-maze), [MultiON](https://github.com/saimwani/multiON) | Navigation benchmarks for spatial/semantic map memory | These already study navigation memory; this package is scoped to localized static grids and explicit serialized bytes |
| [Habitat-Lab](https://github.com/facebookresearch/habitat-lab) | Extensible embodied tasks, metrics, episode specifications and learned/nonlearned evaluation | Our adapter supplies a narrower grid workflow and content identity convention, not a replacement robotics simulator |
| [POPGym Arcade](https://github.com/bolt-research/popgym_arcade) | Memory-state interface, saliency, recall and perturbation analyses | Our checks concern declared-byte bounds and action/output agreement; memory diagnostics themselves are established |
| [SB3-contrib](https://sb3-contrib.readthedocs.io/en/master/modules/ppo_recurrent.html), [RLlib](https://docs.ray.io/en/latest/rllib/checkpoints.html) | Explicit recurrent state, model/component saving and restoration | Serialization and new-instance restoration are not original mechanisms; we connect a specific per-decision contract to grid records |
| [Sacred](https://sacred.readthedocs.io/en/stable/collected_information.html), [ReproZip](https://docs.reprozip.org/en/latest/packing.html) | Experiment/source tracking or execution-dependency capture and packaging | Complementary tools; our entry-module snapshots do not replace a complete dependency archive |
| [OctoMap](https://github.com/OctoMap/octomap), [RTAB-Map](https://github.com/introlab/rtabmap) | Map compression/storage measurement or working-memory management | Maps, working-memory nodes, external databases and the full declared cross-decision payload are distinct accounting objects; no native adapters are claimed |

The integration is replaceable with custom scripts and existing frameworks.
StateBudget-Nav provides an implemented path for trusted controllers: declare
retained bytes, run matched grid tasks, preserve local decision inputs and
compare actions/output digests after restart. See RESEARCH_WORKFLOW.md for what
the user supplies and what is reused.

Memory size, retained facts, navigation results and audit coverage answer
different questions. A smaller code stream does not imply a better closed-loop
trajectory. A complete replay of recorded decisions does not establish absence
of hidden information on untested inputs or task-specific data in free constants.
Use a reviewed scientific contract, code review and accurate coverage reports.

External-controller integration examples are author-side checks. A documented
external participant trial is separate evidence of use, not broad adoption or
a benchmark victory. This software introduces no new compression/navigation
algorithm and claims no measured reduction in developer time.
