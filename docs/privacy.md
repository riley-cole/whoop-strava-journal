# Privacy Policy

**whoop-journal** — Last updated: March 29, 2026

## What this tool does

whoop-journal is an open-source script that runs locally on your computer. It connects to the Whoop and Strava APIs to pull your health and activity data, then writes it into files on your local filesystem (Obsidian vault).

## Data collection

This tool **does not collect, transmit, or store your data anywhere except your own computer.** Specifically:

- No data is sent to any server operated by the developer
- No analytics or telemetry of any kind
- No cookies, tracking, or user accounts
- No cloud storage or remote databases

## Data that stays on your machine

The following data is stored locally in `~/.whoop-journal/`:

- **OAuth tokens** for Whoop and Strava (used to authenticate API requests)
- **Configuration** (your vault path and API client IDs)

Your health data (recovery scores, sleep data, strain, activities) is written directly into your Obsidian vault as markdown files. It never leaves your machine.

## Third-party APIs

This tool makes authenticated API requests to:

- **Whoop API** (api.prod.whoop.com) — governed by [Whoop's Privacy Policy](https://www.whoop.com/privacy/)
- **Strava API** (strava.com/api/v3) — governed by [Strava's Privacy Policy](https://www.strava.com/legal/privacy)

Your use of those services is subject to their respective privacy policies.

## Open source

The complete source code is available at [github.com/riley-cole/whoop-journal](https://github.com/riley-cole/whoop-journal). You can verify every claim in this policy by reading the code.

## Contact

For questions about this privacy policy, open an issue on GitHub or contact the developer through the repository.
