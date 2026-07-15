# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Poll Lidarr's download queue on a configurable interval and, for any item
  with an actual import failure (`trackedDownloadState` of `importFailed`),
  blocklist the release and let Lidarr automatically search for a
  replacement.

## [0.1.0] - 2026-07-15

### Added

- Initial project scaffold.

[Unreleased]: https://github.com/drachenhort/lidarr-watchdog/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/drachenhort/lidarr-watchdog/releases/tag/v0.1.0
