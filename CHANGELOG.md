# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-07-15

### Added

- GitHub Actions workflow to build and publish the Docker image to
  `ghcr.io/drachenhort/lidarr-watchdog` on every `vX.Y.Z` release tag.

## [0.3.0] - 2026-07-15

### Added

- GitHub Actions workflow to run the test suite on push and pull request.
- Web dashboard (FastAPI) showing the last queue check and recent blocklist
  events, backed by a SQLite history store. Runs alongside the polling loop
  in the same process, ready to run in a container.
- Dockerfile (multi-stage build) for running lidarr-watchdog in a container.

## [0.2.0] - 2026-07-15

### Added

- Poll Lidarr's download queue on a configurable interval and, for any item
  with an actual import failure (`trackedDownloadState` of `importFailed`),
  blocklist the release and let Lidarr automatically search for a
  replacement.

## [0.1.0] - 2026-07-15

### Added

- Initial project scaffold.

[Unreleased]: https://github.com/drachenhort/lidarr-watchdog/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/drachenhort/lidarr-watchdog/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/drachenhort/lidarr-watchdog/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/drachenhort/lidarr-watchdog/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/drachenhort/lidarr-watchdog/releases/tag/v0.1.0
