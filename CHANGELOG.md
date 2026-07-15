# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.9.0] - 2026-07-15

### Added

- Optional HTTP Basic Auth for the dashboard and Settings page, enabled by
  setting both `LIDARR_WATCHDOG_USERNAME` and `LIDARR_WATCHDOG_PASSWORD`.
  Credentials are env-var only (not editable via Settings), and `/healthz`
  stays open for container health checks. Off by default, matching prior
  behavior.
- `LIDARR_WATCHDOG_SKIP_AUTH_FOR_LOCAL` to skip auth for clients connecting
  from a private/local IP address, while still requiring it for everyone
  else. Only trusts the direct TCP peer address, never proxy headers like
  `X-Forwarded-For` — see README for the reverse-proxy caveat.
- `/login` page as an optional alternative to the native Basic Auth
  browser prompt: a proper HTML form that sets a session cookie on
  success, with a "Log out" link in the nav (`POST /logout`). Basic Auth
  keeps working exactly as before regardless of whether `/login` is ever
  used. Sessions don't survive a process restart.

### Changed

- Blocklist event messages are now shortened on the dashboard (e.g. "Album
  match is not close enough: 27.6 % vs 80 % [...]" → "Album match is not
  close enough"), with the full original message available as a native
  hover tooltip on truncated ones. Already-short messages like "Has
  missing tracks" are shown unchanged.

## [0.8.0] - 2026-07-15

### Added

- Optional automatic denial of executable files (`.exe`/`.msi`/`.bat`/
  `.cmd`/`.com`/`.scr`/`.vbs`/`.ps1`) found in the queue, toggleable from
  Settings independently of the archive-denial toggle — blocklists and
  requeues them even before Lidarr flags them as a failed import.
- Settings' check interval can now be entered in seconds, minutes, hours,
  or days instead of only raw seconds; the dashboard displays it in the
  most readable unit (e.g. "5 minutes" instead of "300s").
- "Run now" button on the dashboard to trigger an on-demand queue check
  immediately instead of waiting for the next scheduled poll.

### Changed

- Redesigned the dashboard/settings UI: card shadows and an accent color
  instead of flat borders, a pill-style nav with an active-page indicator,
  a monospace scrollable panel for error tracebacks, and full dark-mode
  support via `prefers-color-scheme`.
- Recent blocklist events table and the "Last check" timestamp now show
  `YYYY-MM-DD HH:MM` instead of the full ISO 8601 string with
  seconds/microseconds/offset.

## [0.7.0] - 2026-07-15

### Added

- `PUID`/`PGID` env vars (default `1000`/`1000`) for the Docker image. The
  container now starts as root, adjusts its internal user to the given
  IDs, fixes `/config` ownership, and drops privileges before running the
  app — so a bind-mounted host directory owned by a different or
  Docker-auto-created (root) user no longer causes "unable to open
  database file" and doesn't require manually `chown`-ing the host path.

## [0.6.0] - 2026-07-15

### Changed

- **Breaking (Docker):** the container's data directory moved from `/data`
  to `/config` (matching the Lidarr/Sonarr/Radarr convention), so the
  default `LIDARR_WATCHDOG_DB_PATH` is now `/config/lidarr-watchdog.db`.
  If you have an existing volume mounted at `/data`, remount it at
  `/config` (or move its contents) when upgrading, or your settings and
  history will appear reset.

### Fixed

- Saving Settings without an API key no longer silently leaves Lidarr
  unconfigured. This could happen after using "Test connection" (which
  never persists) and then clicking "Save settings" without retyping the
  key into the now-blank field — Save now requires an API key on first
  setup and rejects the save with a clear error instead.

## [0.5.0] - 2026-07-15

### Added

- Settings page (`/settings`) to configure the Lidarr URL, API key, check
  interval, and a new "deny archive files" toggle at runtime, stored in
  SQLite — no restart required. Includes a "Test connection" action that
  checks the Lidarr connection without saving. `LIDARR_URL`/
  `LIDARR_API_KEY`/`LIDARR_WATCHDOG_POLL_INTERVAL` env vars now only seed
  these settings on first run rather than being required.
- Optional automatic denial of archive files (`.rar`/`.zip`/`.7z`) found in
  the queue, toggleable from Settings — blocklists and requeues them even
  before Lidarr flags them as a failed import.

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

[Unreleased]: https://github.com/drachenhort/lidarr-watchdog/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/drachenhort/lidarr-watchdog/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/drachenhort/lidarr-watchdog/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/drachenhort/lidarr-watchdog/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/drachenhort/lidarr-watchdog/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/drachenhort/lidarr-watchdog/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/drachenhort/lidarr-watchdog/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/drachenhort/lidarr-watchdog/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/drachenhort/lidarr-watchdog/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/drachenhort/lidarr-watchdog/releases/tag/v0.1.0
