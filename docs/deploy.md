# Deploy: worker topology

Two workers share the work, split by what they're allowed to touch:

| Worker | Where | Runs | Queue |
|---|---|---|---|
| orchestrator (`workers/orchestrator.py`) | Docker (`worker` service) | ALL workflows + persistence activities (SQLite gift history, session stats) | `satisfactory-bot` (workflow tasks) + `satisfactory-persist` |
| game worker (`workers/worker.py`) | host desktop session | game-driving activities (screen capture, uinput, KWin focus) | `satisfactory-bot` (activity tasks) |

Temporal polls workflow tasks and activity tasks independently, so both
workers share the `satisfactory-bot` queue without conflict: the container
never registers game activities, the host never registers workflows.

**If the host game worker is down**, workflows keep running in Docker and
game activities simply wait in the queue (then hit their
`schedule_to_close_timeout` / retry policy). Start the host worker and the
farm resumes — no state lost.

## Bring everything up

```bash
docker compose up -d --build     # temporal + UI + postgres + orchestrator worker
uv run python workers/worker.py  # host game worker (needs the desktop session)
uv run python trigger_gift_farm.py
```

## Host game worker as a systemd user service (auto-restart)

`~/.config/systemd/user/satisfactory-game-worker.service`:

```ini
[Unit]
Description=Satisfactory bot game worker (Temporal activities)
After=graphical-session.target

[Service]
WorkingDirectory=%h/Projects/github/satisfactory-ai
ExecStart=%h/.local/bin/uv run python workers/worker.py
Restart=always
RestartSec=5

[Install]
WantedBy=graphical-session.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now satisfactory-game-worker
journalctl --user -u satisfactory-game-worker -f
```

Note: it must run inside your graphical session (Wayland/KWin, uinput). If
uinput permissions are an issue, make sure your user can write
`/dev/uinput` (udev rule or `input` group, depending on distro).

## Gift history

`stats/gift_history.db` (SQLite, bind-mounted into the worker container).
Every per-doggo check is recorded — collected or empty — with timestamp,
OCR'd item name, slot diff and icon-crop path:

```bash
sqlite3 stats/gift_history.db \
  "SELECT doggo, SUM(collected), COUNT(*) FROM gift_checks GROUP BY doggo"
```

`utils/gift_db.py` also has `gift_intervals(doggo)` (seconds between gifts,
for tuning the cycle interval) and `summary()` (totals per doggo/item) for
future report tooling.
