"""Verify the extension path and local sensor boundary, not policy superiority."""
from statebudget_nav.examples.custom_grid import WORLD, local_frame, run


def test_custom_adapter_hides_remote_goal_and_replays_plugin(tmp_path):
    frame = local_frame(WORLD, 10, 0)
    assert not frame.goals
    assert len(frame.cells) == 5
    assert 52 not in dict(frame.cells)  # the remote goal is evaluator-private
    result = run(tmp_path / 'extension', audit_stride=10)
    assert result['success']
    assert result['max_state_bytes'] == result['budget'] == 4
    assert result['audit']['all_passed']
