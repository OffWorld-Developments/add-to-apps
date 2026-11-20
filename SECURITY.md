# Security

Version 0.1.x is the initial development series. Security fixes should target the
latest revision; no older stable series is currently maintained.

The extension runs with the current user's permissions. It does not request root,
run an executable when adding it, upload data, or download icons. Selecting
**Add to Applications** can grant owner execute permission to a recognized program
owned by the current user. Launching the new shortcut executes that program with
the same privileges as any other application you start.

Use **Security → Report a vulnerability** in this repository to contact the
maintainer privately. If private reporting is unavailable, open an issue asking
for a secure contact channel without including the vulnerability details.

Relevant checks cover literal filename handling, desktop field-code injection,
unmanaged files, symlinks, stale Undo, corrupt state, and installation manifests.
These checks do not constitute a security audit of the selected executable.

CI scans the fetched Git history, working files and generated source archives with
Gitleaks before saving release artifacts. Scanner output redacts detected values.
See [the pre-publication audit](docs/SECURITY-AUDIT.md) for the initial audit scope.
