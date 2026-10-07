# Sourced by the unchanged native runner. Keep its SSH setup and teardown.
. /opt/pwntools-setup-local-ssh-native.sh

# Pwntools may mutate or remove cached ELF files during public doctests.
# The image-owned seed is read-only; each run gets a writable tmpfs copy.
(cd /opt/pwntools-offline && sha256sum --check --strict SHA256SUMS >/dev/null) || exit 125
export XDG_CACHE_HOME=/tmp/pwntools-offline-cache
pwntools_cache_version=$(python -c 'import sys; print("%d.%d" % sys.version_info[:2])') || exit 125
mkdir -p "$XDG_CACHE_HOME/.pwntools-cache-$pwntools_cache_version" || exit 125
cp -R /opt/pwntools-offline/data/cache-seed/. "$XDG_CACHE_HOME/.pwntools-cache-$pwntools_cache_version/" || exit 125
chmod -R u+w "$XDG_CACHE_HOME" || exit 125
