# whoop-journal

Pull Whoop and Strava data into Obsidian journal entries. Recovery, sleep, strain, and running stats — written to YAML frontmatter (for Dataview/Heatmap Tracker queries) and a readable markdown section.

**Zero external dependencies.** Pure Python stdlib. Works with Python 3.8+ on any Mac or Linux system.

## What it does

Runs once daily (manually or via scheduled task). For a given date:

1. Pulls **Whoop** data: recovery score, HRV, resting HR, SpO2, skin temp, sleep stages, strain, workouts
2. Pulls **Strava** data: distance, pace, elevation, heart rate for each activity
3. Merges both into your Obsidian journal entry for that date
4. If no journal entry exists, creates one from your template

Activities from both sources are matched by time — a morning run shows Strava's distance/pace alongside Whoop's strain score.

## Example output

```yaml
---
type: journal
date: "2026-03-28"
day: "Saturday"
tags:
  - journal
whoop-recovery: 84
whoop-hrv: 68.5
whoop-rhr: 52
whoop-strain: 12.4
whoop-sleep-score: 91
whoop-sleep-hours: 7.6
strava-miles: 4.2
strava-runs: 1
---
```

```markdown
## Whoop

**Recovery: 84%** | HRV: 68.5 ms | Resting HR: 52 bpm | SpO2: 97% | Skin Temp: 33.2C

### Sleep
7h 36m in bed (91% performance, 94.2% efficiency)
Light: 3h 12m | Deep: 1h 48m | REM: 2h 06m | Awake: 30m
Cycles: 4 | Disturbances: 8 | Respiratory Rate: 15.2 rpm

### Strain
Day Strain: 12.4 | Avg HR: 72 bpm | Max HR: 165 bpm | 2,150 kcal

### Activities
**Morning Run** 6:30 AM — 4.2 mi, 8:12/mi pace, 32:45 elapsed
↑ 185 ft | HR avg 148 / max 172 | Strain: 14.2
```

## Setup

### 1. Register API apps

**Whoop:** Go to [developer-dashboard.whoop.com](https://developer-dashboard.whoop.com). Create a team, create an app. Set redirect URI to `http://localhost:1234`. Add scopes: `read:recovery`, `read:cycles`, `read:sleep`, `read:workout`.

**Strava:** Go to [strava.com/settings/api](https://www.strava.com/settings/api). Create an application. Set Authorization Callback Domain to `localhost`.

### 2. Run setup

```bash
python3 setup.py
```

The setup script:
- Prompts for your client IDs and secrets
- Opens your browser for OAuth authorization (both services)
- Catches the callbacks automatically (local HTTP server)
- Saves tokens securely to `~/.whoop-journal/`
- Tests both connections

You can set up one service at a time with `--whoop-only` or `--strava-only`.

### 3. Sync

```bash
python3 bin/sync.py              # Yesterday's data
python3 bin/sync.py --date 2026-03-28  # Specific date
python3 bin/sync.py --verbose    # Debug output
```

### 4. Schedule (optional)

If using Claude Code, create a scheduled task to run this daily at 8 AM.

## Configuration

All config and tokens live at `~/.whoop-journal/`:

| File | Purpose |
|------|---------|
| `config.json` | Vault path, journal subfolder, API client IDs/secrets |
| `whoop_tokens.json` | Whoop OAuth tokens (auto-refreshed) |
| `strava_tokens.json` | Strava OAuth tokens (auto-refreshed) |

All files are created with restrictive permissions (600/700).

## Flags

| Flag | Effect |
|------|--------|
| `--date YYYY-MM-DD` | Sync a specific date (default: yesterday) |
| `--verbose` | Show debug output |
| `--skip-existing` | Don't overwrite dates that already have data |
| `--whoop-only` | Skip Strava |
| `--strava-only` | Skip Whoop |

## How it works

- **Idempotent**: Running twice for the same date produces identical output
- **Partial data**: If one service fails, the other still writes. Missing data = omitted fields
- **Atomic writes**: Uses temp file + rename to prevent corruption
- **Token refresh**: Handles expired tokens automatically, saves new tokens immediately
- **Activity matching**: Whoop workouts and Strava activities are matched by overlapping time windows (within 30 min). Strava provides distance/pace/elevation; Whoop provides strain

## Requirements

- Python 3.8+ (macOS system Python works)
- Whoop membership + developer app
- Strava account + API app
- An Obsidian vault with journal entries as `YYYY-MM-DD.md` files

## License

MIT
