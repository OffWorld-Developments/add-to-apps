# Pre-publication audit — November 20, 2026

Repository: [OffWorld-Developments/add-to-apps](https://github.com/OffWorld-Developments/add-to-apps).

## Results

No credential or private-key findings were detected by Gitleaks in:

- All five reachable commits, including fetched branches, tags and the retained
  Dependabot PR refs, using `--all --full-history`.
- The working directory, including uncommitted changes and local release archives,
  with archive traversal enabled.
- All 73 local Git objects, including commit messages and unreferenced objects,
  plus the local Git configuration.

The scanner used the default rules from the Arch Linux Gitleaks 8.30.1 package.
The package signature was verified against the installed Arch public keyring.
The scans ran locally; source files and credentials were not uploaded. Reports
were redacted and kept outside the repository. No existing suppression file or
inline allow comment was used to suppress the audit results.

The tracked-file inventory contains source code, tests, documentation, license and
repository configuration. Environment files, private keys, token stores, build
outputs and bytecode caches are not tracked. Release packaging selects source
files explicitly and excludes Git metadata, caches and local build output.

## Attribution

Existing commit metadata contains the owner's `offworld.dev` author email.
The owner explicitly chose to retain that attribution. It will be visible with
the public commits. No history rewrite was performed.

## Changes made

- Updated `origin` to the renamed repository and verified a successful fetch.
- Updated the README and project links to the canonical repository URL.
- Added ignore patterns for common credential stores, private keys and local logs.
- Added redacted history and source/archive secret scans to CI. Checkout fetches
  the full history so the history scan is not limited to one commit.
- Kept installed package/application identifiers stable for existing users.

## Scope limits

This records automated credential detection and a source/file-inventory review;
it is not a guarantee that every possible secret or private datum can be detected.

The GitHub connection could not access the organization repository. Git history
was fetched over the configured SSH remote instead. This audit does not cover
hosted issues, PR conversations, Actions logs, old workflow artifacts, release
attachments, repository settings, GitHub-managed secrets or a wiki. Those hosted
surfaces need an authorized review before changing visibility if they have been
used for private information.

Local remote changes and audit preparation do not publish code or change GitHub
visibility. CI scan steps will run after these workflow changes are committed and
pushed; a hosted result has not been observed for those new steps.
