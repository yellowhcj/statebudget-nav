"""Regression: cross-system path spelling must not hide source drift."""
from copy import deepcopy
import pytest
from statebudget_nav._runtime_identity import portable_source_hashes, assert_runtime_matches
from statebudget_nav.study import runtime_identity


def identity():
    return dict(package_version='0.1.0.dev10', dependencies={'numpy': 'example'},
                package_files_sha256={'_core/controller.py': 'exact-hash'},
                plugin_entry_modules={'plugin': {'origin': '/linux/plugin.py', 'sha256': 'plugin-hash'}})


def test_legacy_windows_and_linux_keys_match_without_ignoring_digests():
    old = identity()
    old['package_files_sha256'] = {'_core\\controller.py': 'exact-hash'}
    old['plugin_entry_modules']['plugin']['origin'] = 'C:\\new-place\\plugin.py'
    assert_runtime_matches(old, identity())


@pytest.mark.parametrize('change,match', [
    ('package_version', 'package_version'), ('dependencies', 'dependencies'),
    ('source', 'package_files_sha256'), ('plugin', 'plugin entry'),
    ('missing_source', 'package_files_sha256')])
def test_real_drift_still_rejected(change, match):
    current = deepcopy(identity())
    if change == 'package_version': current[change] = '0.1.0.dev9'
    elif change == 'dependencies': current[change]['numpy'] = 'different'
    elif change == 'source': current['package_files_sha256']['_core/controller.py'] = 'different'
    elif change == 'missing_source': current['package_files_sha256'] = {}
    else: current['plugin_entry_modules']['plugin']['sha256'] = 'different'
    with pytest.raises(ValueError, match=match): assert_runtime_matches(identity(), current)


@pytest.mark.parametrize('name', ['../x.py', '/x.py', 'C:\\x.py', './x.py', 'a//x.py'])
def test_invalid_identity_paths_rejected(name):
    with pytest.raises(ValueError, match='invalid'): portable_source_hashes({name: 'hash'})


def test_colliding_legacy_spellings_do_not_merge_even_with_equal_hash():
    with pytest.raises(ValueError, match='ambiguous'):
        portable_source_hashes({'_core/x.py': 'same', '_core\\x.py': 'same'})


def test_generated_runtime_source_keys_use_posix_spelling():
    keys = runtime_identity({'controllers': []})['package_files_sha256']
    assert '_core/controller.py' in keys
    assert all('\\' not in key for key in keys)
