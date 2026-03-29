---
name: whoop-journal
version: 0.1.0
description: |
  Pull Whoop recovery/sleep/strain and Strava activity data into Obsidian
  journal entries. Adds queryable frontmatter (Dataview/Heatmap Tracker)
  and a readable summary section. Zero external dependencies.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
---

# whoop-journal

Syncs Whoop + Strava data into Obsidian journal entries daily.

## Commands

### Sync yesterday (default)
```bash
python3 ~/.claude/skills/whoop-journal/bin/sync.py
```

### Sync a specific date
```bash
python3 ~/.claude/skills/whoop-journal/bin/sync.py --date 2026-03-28
```

### Backfill a date range
Run sync.py for each date. Use `--skip-existing` to avoid overwriting:
```bash
for d in $(python3 -c "from datetime import date, timedelta; d=date(2026,3,1); [print((d+timedelta(i)).isoformat()) for i in range(28)]"); do
  python3 ~/.claude/skills/whoop-journal/bin/sync.py --date "$d" --skip-existing
done
```

### Test connections
```bash
python3 ~/.claude/skills/whoop-journal/bin/setup.py --test
```

### Re-authenticate
```bash
python3 ~/.claude/skills/whoop-journal/bin/setup.py --reauth
```

## Setup (first time)

1. Register a Whoop developer app at https://developer-dashboard.whoop.com
   - Redirect URI: `http://localhost:1234`
   - Scopes: read:recovery, read:cycles, read:sleep, read:workout

2. Register a Strava API app at https://www.strava.com/settings/api
   - Authorization Callback Domain: `localhost`

3. Run the setup script:
   ```bash
   python3 ~/.claude/skills/whoop-journal/bin/setup.py
   ```
   It will prompt for credentials, open browsers for OAuth, and save tokens.

## Flags

| Flag | Effect |
|------|--------|
| `--date YYYY-MM-DD` | Target a specific date instead of yesterday |
| `--verbose` | Debug logging |
| `--skip-existing` | Skip dates that already have whoop/strava data |
| `--whoop-only` | Only pull Whoop data |
| `--strava-only` | Only pull Strava data |

## Data Written

**Frontmatter keys** (omitted when unavailable):
- `whoop-recovery` (0-100), `whoop-hrv` (ms), `whoop-rhr` (bpm)
- `whoop-strain` (0-21), `whoop-sleep-score` (0-100), `whoop-sleep-hours`
- `strava-miles`, `strava-runs`

**Body section** (`## Whoop`): Recovery summary, sleep stages, strain, activities.
Strava activities show distance/pace/elevation. Whoop workouts show strain/HR.
When both exist for the same workout, they merge (Strava for distance, Whoop for strain).

## File Locations

| What | Where |
|------|-------|
| Config | `~/.whoop-journal/config.json` |
| Whoop tokens | `~/.whoop-journal/whoop_tokens.json` |
| Strava tokens | `~/.whoop-journal/strava_tokens.json` |
| Journal output | `{vault_path}/{journal_path}/YYYY-MM-DD.md` |

All credential files are mode 600 (owner-only). The `~/.whoop-journal/` directory is mode 700.

## Troubleshooting

**"Token refresh failed"**: Tokens expired beyond refresh. Run `setup.py --reauth`.

**"No data retrieved"**: Check the date. Whoop scores overnight sleep on the day you wake up. If you're syncing "yesterday" at 6 AM, recovery might still be pending — the script handles this gracefully (shows "Pending").

**"Config not found"**: Run `setup.py` to create the initial config.

**Strava shows no activities**: Strava filters by the activity's start date in UTC. If you ran at 11 PM local, the UTC date might be "tomorrow." Try syncing the adjacent date.

## Scheduled Task

To run this daily at 8 AM:
```
Create a scheduled task:
  taskId: whoop-journal-sync
  cronExpression: 3 8 * * *
  prompt: Run python3 ~/.claude/skills/whoop-journal/bin/sync.py and report any errors.
```
