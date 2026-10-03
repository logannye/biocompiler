# Frozen migration work for a fresh session

Start with [the current handoff](../../migration-session-handoff.md) and the
[language roadmap](../../language-migration-roadmap.md).

`drafts.tar.gz` intentionally preserves unfinished source, exact original
observations, review notes and failure evidence. It is a handoff artifact, not a
native distribution or an accepted implementation. `manifest.json` binds every
member and the complete archive. Caches, compiled bytecode and native build
trees are excluded. Already integrated source is retained in ordinary Git history.

From the repository root, verify the packet without writing:

```sh
python3 tools/restore_migration_handoff.py
```

Restore to the original ignored `generated/migration-next/` locations:

```sh
python3 tools/restore_migration_handoff.py --restore
```

The restorer accepts identical existing files and refuses conflicting files or
symlinked destinations. To inspect a frozen version beside newer local work, use
`--restore --root /absolute/path/to/a/fresh/directory`. Nothing applies patches,
imports draft modules, starts native executables or changes the production backend.

Read each draft's status before use. Several patches predate later changes to
shared callback modules. Compose against current source and revalidate rather
than applying those patches blindly. The archive is deliberately immutable;
future progress belongs in a new checkpoint or the normal source tree.
