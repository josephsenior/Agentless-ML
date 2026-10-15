"""Verify public Git blobs before supplying Infogami to a disposable workspace."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import sys

COMMIT = 'd918e184ca1b0de7e8d3b02ec7b7dc4a08453cea'


def verify_and_supply(manifest, source, destination):
    if manifest.get('commit') != COMMIT or not manifest.get('files'):
        raise ValueError('wrong or empty public Infogami pin')
    verified = []
    names = set()
    for entry in manifest['files']:
        name, mode = entry['path'], entry['mode']
        pure = PurePosixPath(name)
        if (pure.is_absolute() or '..' in pure.parts or '.git' in pure.parts
                or str(pure) != name or '\\' in name or name in names
                or mode not in ('100644', '100755')):
            raise ValueError('unsafe or unsupported public file entry')
        names.add(name)
        path = source / name
        if any(part.is_symlink() for part in (path, *path.parents) if part != source.parent):
            raise ValueError('image file must not resolve through symlinks')
        metadata = path.stat()
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError('image entry is not a regular file')
        content = path.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
        if blob != entry['blob'] or bool(metadata.st_mode & 0o111) != (mode == '100755'):
            raise ValueError('image file differs from pinned public blob: ' + name)
        verified.append((entry, content))
    # Nothing is supplied until all public files have been checked. Image extras
    # (including generated files or links) are intentionally not copied.
    if destination.exists():
        if destination.is_symlink() or not destination.is_dir() or any(destination.iterdir()):
            raise ValueError('submodule destination must be absent or empty')
    else:
        destination.mkdir(parents=True)
    hashes = {}
    for entry, content in verified:
        target = destination / entry['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        target.chmod(0o755 if entry['mode'] == '100755' else 0o644)
        hashes[entry['path']] = hashlib.sha256(content).hexdigest()
    return dict(commit=COMMIT, files_verified=len(verified), files_supplied=len(verified),
                image_extras_copied=False, public_file_sha256=hashes)


if __name__ == '__main__':
    manifest_path, source_path, destination_path = map(Path, sys.argv[1:])
    print(json.dumps(verify_and_supply(json.loads(manifest_path.read_bytes()), source_path, destination_path)))
