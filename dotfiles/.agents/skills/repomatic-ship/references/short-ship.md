# Repairing a short ship

When the binary matrix came up short, say so in the step 7 report and name the platforms the version will lose. Publishing is what locks the asset list, so this is the last moment the gap is cheap to record; afterwards it is a permanent property of that version. Shipping short is intended behavior and never a reason to hold the release.

Three artifacts then keep advertising binaries that are not there, each needing a hand *after* the merge:

- The version's **changelog section**, which takes a `> [!WARNING]` naming the gap. Write it as a hand-written admonition in which no line starts with `` > `X.Y.Z` is ``. It then lands in the editorial slot `fix-changelog` preserves, not the availability slot it regenerates.
- The **GitHub release body**, rebuilt from that section. Immutability locks the assets and the tag, not the notes, so this stays editable after publishing. `sync-github-releases` is the mechanism, but it skips drafts and caches the release list for 24h, so a same-day fix goes through `gh release edit --notes-file` with the body `build_expected_body` renders. Both converge on the same text, so a later CI sync is a no-op rather than a clobber.
- **`docs/install.md`**, whose download URLs the freeze pins to the version being released, optimistically: the freeze commit is what triggers the build, so it cannot know whether the binaries will land. Re-point them at the last release that carries binaries via `PrepareRelease.freeze_install_download_urls`, and the next release's freeze ratchets them forward again. `lint-repo`'s `check_install_guide_downloads` reports the gap but never repairs it, since an automated rewrite driven by a single API read could downgrade a healthy install page on a flaky response.

Report the three as follow-ups. Do not perform them: they land after a merge this skill does not make.

```{note}
Upstream only: the release PR is rebase-merged, so its freeze and unfreeze commits arrive in a single push, and GitHub Actions reads workflow files from that push's head. `kdeldycke/repomatic`'s own release lane therefore always runs the **unfrozen** workflow content, whatever the freeze wrote into the release commit. A job that assumes the frozen `uvx 'repomatic==X.Y.Z'` form is what executes (and drops its checkout on that basis) dies on `Failed to spawn: repomatic`. Only downstream repos, which call the reusable workflow at its tag, ever run the frozen form.
```
