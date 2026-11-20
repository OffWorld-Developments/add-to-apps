# Publishing

## Distribution

Add to Apps is a **GNOME Files / Nautilus extension**. Its Python loader
is installed into Nautilus's extension directory. The supported release artifact
is a source archive containing the per-user installer and uninstaller.

**The current feature cannot be uploaded to extensions.gnome.org.** That site
distributes GNOME Shell extensions, with a JavaScript `extension.js` entry point
and `metadata.json`. Its review guidelines also put Python modules outside the
review scope. A repository URL is necessary for a Shell submission but does not
make a Files extension eligible.

Keep the existing right-click feature as the initial release. Repository releases
are the first distribution channel; native distribution packages can follow.
Any future Shell integration should be separately designed, tested, and packaged.
Do not ship an empty Shell wrapper solely to obtain a listing.

References:

- [Shell extension format](https://gjs.guide/extensions/overview/anatomy.html)
- [Scripts and binaries review rules](https://gjs.guide/extensions/review-guidelines/review-guidelines.html#scripts-and-binaries)
- [Choosing the appropriate integration](https://gjs.guide/extensions/overview/updates-and-breakage.html)

## Prepare the repository

Repository: [OffWorld-Developments/add-to-apps](https://github.com/OffWorld-Developments/add-to-apps).

The configured SSH remote is `git@github.com:OffWorld-Developments/add-to-apps.git`.
The repository rename does not change installed package names, application IDs or
existing launcher files. Source archives keep the `add-to-applications-*` name.

Suggested description:

> Add standalone executables to GNOME Applications with one click in Files.

Suggested topics: `gnome`, `nautilus-extension`, `desktop-entry`, `linux`, `python`.

Before making the repository public:

1. Confirm the intended visibility and retain the GPL-3.0-or-later license.
2. Confirm the application ID in `src/add_to_applications/__init__.py`. It is
   already used by existing installations and Undo notifications; changing it
   requires an upgrade/migration plan. A repository name change does not require
   an application ID change.
3. Review the files to be committed. Ignore caches, local environments, secrets,
   and `dist/`; attach generated archives to releases instead of committing them.
4. Enable Issues and private vulnerability reporting in the repository settings.
5. After the first push, run the **Validate** workflow and require its successful
   result for changes to the default branch. Hosted CI has not run until there is
   an actual repository and a workflow run.

Review [the pre-publication audit](SECURITY-AUDIT.md), including its scope and the
hosted content that could not be inspected. Updating the local remote does not
push code or change the repository's visibility.

## Build and inspect a release

From the repository root:

```sh
ruff check .
ruff format --check .
python3 -m pytest -q
python3 tools/package.py --tag v0.1.0
```

The package command checks the tag against both version declarations. It writes:

- `dist/add-to-applications-0.1.0.tar.gz`
- `dist/add-to-applications-0.1.0.tar.gz.sha256`

The archive excludes repository metadata, local caches, environments and build
outputs. It includes the source, license, installer, documentation, tests and CI
configuration. Verify it before upload:

```sh
cd dist
sha256sum --check add-to-applications-0.1.0.tar.gz.sha256
```

The **Validate** workflow also saves these files as the `source-release` artifact
for 14 days. Workflow artifacts are build outputs, not published GitHub releases.

## Draft release

1. Complete the applicable checks in [RELEASING.md](RELEASING.md) and record actual
   results in [VALIDATION.md](VALIDATION.md). Do not claim untested distributions
   or accessibility checks.
2. Confirm the version, update the changelog's release date, and commit the changes.
3. Create and push the matching `v0.1.0` tag. Tag builds reject version mismatches.
4. Create a **draft** release from that tag, using
   [the prepared release notes](releases/v0.1.0.md), and attach the archive and its
   checksum. Review the rendered notes and download/install/uninstall the attached
   artifact in a disposable account before publishing.
5. Publish when the owner is ready. No workflow in this project publishes a release
   automatically or holds write permission to repository contents.

Keep homepage, bug-report and security links in sync with the repository URL.
Record the tag commit and hosted CI run in the release notes.
