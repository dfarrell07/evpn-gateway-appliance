# Markdown CI tooling

`make check-markdown` runs the [markdownlint-cli2](https://github.com/DavidAnson/markdownlint-cli2)
pinned here with the required root [configuration](../../.markdownlint-cli2.jsonc).
[Dockerfile.ci](../../Dockerfile.ci) installs it from this directory's
[npm lock](package-lock.json) with install scripts disabled. To lint on the host:

```bash
npm ci --prefix ci/markdownlint --ignore-scripts --engine-strict
PATH="$PWD/ci/markdownlint/node_modules/.bin:$PATH" make check-markdown USE_IMAGE=0
```

To change a version, edit `package.json`, then update the lock with
`npm install --prefix ci/markdownlint --package-lock-only --ignore-scripts`.

The `smol-toml` override takes the fix for
[GHSA-r4xh-jqrq-34v2](https://github.com/advisories/GHSA-r4xh-jqrq-34v2); remove it
once markdownlint-cli2 depends on smol-toml 1.9.0 or later. The
[braces](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) and
[KaTeX](https://github.com/advisories/GHSA-238p-pmpm-9mq7) advisories have no fix within
markdownlint-cli2's dependency ranges. None of the three is reachable: the check reads
no TOML configuration, passes literal paths and renders no HTML.
