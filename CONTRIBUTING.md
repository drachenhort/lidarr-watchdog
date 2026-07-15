# Contributing

## Setup

```sh
python3 -m venv .venv
.venv/bin/pip install -e . pytest
```

## Testing

```sh
.venv/bin/pytest
```

## Versioning

Versions are derived from git tags via `hatch-vcs` (see `pyproject.toml`) —
do not hardcode a version number anywhere. Releases are tagged `vX.Y.Z`.

## Changelog

Add an entry under `[Unreleased]` in `CHANGELOG.md` for any user-facing
change. When cutting a release, move the `[Unreleased]` entries under a new
`[X.Y.Z] - YYYY-MM-DD` heading.

## Pull requests

Keep commits focused and use clear commit messages. Make sure tests pass
before opening a PR.
