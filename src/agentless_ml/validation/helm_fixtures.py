"""Immutable Helm fixture policy; links are created only inside Linux Docker."""

import json

BASE = "42f78ba60edf531d5161e00d9819a7c34d976343"
IMAGES = {
    "helm-array-merge-strategies": "sha256:d8b573f9e37303fb1aeb03efbfbecb84be8ea2dabaefb34f09b66bb6f6c13721",
    "helm-unified-manifest-stream": "sha256:b6915c6766cbfd2a26301adcb79bcb49a0c84bbff4039920378c9ff854c48d2c",
}
SPECIAL_LINKS = {
    "internal/chart/v3/loader/testdata/frobnitz_with_dev_null/null": "/dev/null",
    "pkg/chart/v2/loader/testdata/frobnitz_with_dev_null/null": "/dev/null",
    "internal/third_party/dep/fs/testdata/symlinks/invalid-symlink": "/non/existing/file",
    "internal/third_party/dep/fs/testdata/symlinks/windows-file-symlink":
        "C:/Users/ibrahim/go/src/github.com/golang/dep/internal/fs/testdata/test.file",
}
ALL_LINKS = {
    **SPECIAL_LINKS,
    "internal/third_party/dep/fs/testdata/symlinks/file-symlink": "../test.file",
}

CONTAINER_SETUP = r'''
import json, os, stat
from pathlib import Path
root = Path("/tmp/work")
links = json.loads(LINKS_JSON)
null = Path("/dev/null").lstat()
if not stat.S_ISCHR(null.st_mode) or (os.major(null.st_rdev), os.minor(null.st_rdev)) != (1, 3):
    raise RuntimeError("Helm requires the container's native /dev/null character device")
for relative, target in links.items():
    link = root / relative
    # Require actual directories below the candidate root, not aliases.
    cursor = root
    if not stat.S_ISDIR(cursor.lstat().st_mode) or cursor.is_symlink():
        raise RuntimeError("invalid candidate root")
    for part in link.relative_to(root).parts[:-1]:
        cursor /= part
        if not stat.S_ISDIR(cursor.lstat().st_mode) or cursor.is_symlink():
            raise RuntimeError("Helm fixture parent is not a real candidate directory")
    if os.path.lexists(link):
        raise RuntimeError("refusing to overwrite candidate Helm fixture")
    if target != "/dev/null":
        resolved = Path(target) if target.startswith("/") else link.parent / target
        if os.path.lexists(resolved):
            raise RuntimeError("expected dangling Helm fixture target is present")
for relative, target in links.items():
    link = root / relative
    os.symlink(target, link)
    if not stat.S_ISLNK(link.lstat().st_mode) or os.readlink(link) != target:
        raise RuntimeError("Helm fixture reconstruction mismatch")
print(json.dumps({"profile": "helm-container-fixtures-v1", "links": links}, sort_keys=True))
'''.replace("LINKS_JSON", repr(json.dumps(SPECIAL_LINKS))).strip()
