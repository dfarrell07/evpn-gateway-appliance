# CI helper lint

Ruff and ShellCheck catch common Python and shell mistakes in the repository's
CI helpers. They run through the existing shared `check`/`verify` gate and extend
to matching source files as reviewed imports arrive.

```bash
make lint-python lint-shell
make check OFFLINE=1
```

Make builds and runs `Dockerfile.ci` by default. Host runs use `USE_IMAGE=0` and
need the tool versions pinned in that file. Image builds download packages;
the lint targets run offline and do not modify source.

The targets check Git-selected tracked files and new nonignored files, including
unstaged edits and tracked ignored files. Stage deletions before checking.
Ruff uses isolated configuration and basic `E4,E7,E9,F` rules for Python 3.12;
ShellCheck ignores discovered configuration and `SHELLCHECK_OPTS`. Native inline
exceptions remain source changes to review.

Ruff 0.17.0 includes the upstream fix for existing literal `@` filenames
([argument handling](https://github.com/astral-sh/ruff/blob/5b27c1ccfaa230fb195855f5cf3404a21e3379cd/crates/ruff_command_line/src/lib.rs)).
The target rejects non-file inputs because Ruff otherwise accepts directories
and interprets missing `@` paths as argument files. It also clears
`RUFF_OUTPUT_FILE` to prevent an inherited setting from writing a report over source.
ShellCheck's [`--norc` contract](https://github.com/koalaman/shellcheck/blob/aac0823e6b58f8a499e856e93738082691cbf212/shellcheck.1.md)
does not clear its options environment variable, so the target clears it explicitly.
