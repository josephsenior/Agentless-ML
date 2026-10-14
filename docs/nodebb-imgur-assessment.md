# Imgur package assessment

Status: cache-supplement work is paused following the
[phase-specific network policy review](network-policy.md). The verified inputs
below remain evidence; they are not a requirement to build another image.

On 14 October 2026, the public NodeBB test was blocked at an offline npm
install, not at an Imgur assertion. This assessment checks the public inputs
needed for that operation. It does not build an image or change readiness.

## What the test actually needs

The unchanged `test/plugins.js` installs `nodebb-plugin-imgur@1.0.16`, activates
it, upgrades to `latest`, then uninstalls it. Checking only the old tarball would
miss the upgrade. Both npm and the NodeBB detail response currently identify
`latest` as **5.0.0**; the earlier full-list snapshot agrees.

| Plugin version | Direct dependencies | Resolved packages, including plugin |
| --- | --- | --- |
| 1.0.16 | `request:^2.48.0`, `winston:~0.8.3` | 55 |
| 5.0.0 | `request:^2.88.2` | 48 |

Across both trees there are **56 unique name/version pairs**. Every exact
package metadata response and tarball was downloaded over HTTPS from npm.
Each tarball matches its published SRI and SHA-1, and its package name, version
and dependency declarations match the metadata. Saved files also have SHA-256
pins and were rechecked when the evidence was exported. These checks establish
consistency with the captured registry, not a security audit or verification
of npm registry signatures.

None of these resolved packages declares an install, preinstall or postinstall
script. The locks contain no OS/CPU restrictions, optional or peer dependency
requirements. This reduces platform-specific concerns in the isolated trees;
it says nothing about the rest of NodeBB's dependencies.

The captured NodeBB response lists both required versions as valid. Its name,
repository URL and description match the public test's expected fields. The
existing local registry service does **not** yet serve this new detail route.
It would need the exact captured response at
`/api/v1/plugins/nodebb-plugin-imgur` in a separately reviewed image.

## What this does not prove

Resolution used npm **10.8.2**, copied from the pinned image, with scripts,
audit and funding requests disabled. It ran on Windows with host Node
**22.20.0**, rather than the image's Linux Node **18.20.8**. The isolated
projects contain only the plugin dependency. Their locks are planning inputs,
not replacements for NodeBB's dependency configuration.

The real command is `npm install ... --save` inside NodeBB, followed later by
upgrade and uninstall. npm can reconcile the entire root project, including
development dependencies, and the current setup links existing dependencies
to the read-only image. Extra root metadata, writable paths or lifecycle
requirements may therefore be needed even though these plugin trees verify.
No full-root transaction has been attempted by this assessment.

The previously proposed next step was to assess cache coverage and writable dependency layout for
that exact Linux/root transaction, then build a separately labelled supplement
from reviewed public pins. Keep the original tests, offline network policy and
resource limits. A successful isolated resolution is not a passing baseline.

## Evidence

The [checked-in manifest](../experiments/swe_bench_pro/v2_js_nodebb_upload_path/imgur-assessment-2026-10-14.json)
records exact versions, dependency trees, metadata and tarball URLs, checksums,
registry response fields and toolchain limits. Raw responses, tarballs and locks
remain outside Git under
`output/swe-bench-pro-v2-readiness/2026-10-14-nodebb-imgur-assessment` in the
parent workspace. The resolver's temporary metadata cache is an assessment
artifact, not a built or registered cache supplement.

`tools/assess_nodebb_imgur.py` captures fresh inputs into a new output directory;
`--record-existing ASSESSMENT --evidence DESTINATION` rechecks saved assets and
exports portable evidence without downloads or Docker. No plugin lifecycle
scripts, benchmark tests, image builds or model calls were run. NodeBB remains
**not ready**; the last full attempt remains 3,321 passes and one failure.
