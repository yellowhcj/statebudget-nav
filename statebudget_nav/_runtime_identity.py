"""Portable spelling of source paths, with strict runtime identity checks."""
from pathlib import PurePosixPath, PureWindowsPath


def portable_source_hashes(files):
    """Accept old Windows separators without discarding or merging any entry."""
    result = {}
    for original, digest in files.items():
        name = original.replace('\\', '/')
        if (not name or PurePosixPath(name).is_absolute()
                or PureWindowsPath(name).drive
                or any(part in ('', '.', '..') for part in name.split('/'))):
            raise ValueError('invalid runtime source path: ' + original)
        if name in result:
            raise ValueError('ambiguous runtime source path: ' + name)
        result[name] = digest
    return result


def assert_runtime_matches(recorded, current):
    """Path spelling is portable; versions and all recorded digests stay exact."""
    for key in ('package_version', 'dependencies'):
        if recorded[key] != current[key]:
            raise ValueError('installed runtime identity differs: ' + key)
    if portable_source_hashes(recorded['package_files_sha256']) != portable_source_hashes(current['package_files_sha256']):
        raise ValueError('installed runtime identity differs: package_files_sha256')
    if {k: v['sha256'] for k, v in recorded['plugin_entry_modules'].items()} != {
            k: v['sha256'] for k, v in current['plugin_entry_modules'].items()}:
        raise ValueError('installed plugin entry differs')
