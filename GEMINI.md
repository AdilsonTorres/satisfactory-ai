# Gemini Agent: Project Configuration & Protocols

## 📐 Architecture Map

This project implements an autonomous AFK gameplay bot and orchestrator for the game **Satisfactory**, structured around **Temporal** workflows and activities.

```mermaid
graph TD
    subgraph Host ["Host Environment (GUI & Input Access)"]
        CLI[sbot CLI] -->|Triggers| Client[Temporal Client]
        HostWorker[Host Worker] -->|Runs| GameActivities[Game Control Activities]
        GameActivities -->|Screenshots| MSS[MSS / OpenCV]
        GameActivities -->|Keystrokes / Mouse| Evdev[evdev / pynput]
    end

    subgraph Docker ["Docker Stack (Persistence & Orchestrator)"]
        Orchestrator[Orchestrator Worker] -->|Runs| Workflows[Loop / Orchestrator Workflows]
        Orchestrator -->|Runs| PersistActivities[DB / Save History Activities]
        TemporalServer[Temporal Server 1.30.5] <-->|gRPC| Orchestrator
        TemporalServer <-->|gRPC| HostWorker
        TemporalServer <-->|State DB| PostgreSQL[(PostgreSQL 18)]
        TemporalUI[Temporal UI 2.51.1] -->|Inspects| TemporalServer
    end
```

### 📂 Directory Structure
*   `tools/cli.py` ([cli.py](file:///home/adilson/Projects/github/satisfactory-ai/tools/cli.py)): The main entry point `sbot` for command-line control (planning, triggers, calibration, status).
*   `workflows/`: Temporal Workflows coordinating loops, schedules, and higher-level automation state.
*   `activities/`: Temporal Activities containing concrete execution units (mouse moves, save file backups).
*   `workers/`: Workers dividing task queues:
    *   **Orchestrator Worker** (Runs in Docker): Responsible for workflows and persistence tasks.
    *   **Host Worker** (Runs on Host): Has access to UI sessions, screens, and input devices.
*   `utils/`: Helpers for recipe lists, parsing save files (`save_parser.py`), and analyzing game logs.

---

## 🛠️ Setup Steps

### 1. Requirements
*   Python `>= 3.14`
*   `uv` for Python virtual environment and dependency management
*   Docker & Docker Compose

### 2. Environment Setup
Create a virtual environment and sync dependencies:
```bash
uv sync
```

### 3. Running the Stack
Launch the database, migration pipeline, Temporal server, and local orchestrator worker:
```bash
docker compose up -d
```

### 4. Running the Host Worker
Run the GUI/interaction worker on your local machine (needs display access):
```bash
uv run python workers/worker.py
```

---

## 📦 Core Dependencies
*   `temporalio`: Workflow orchestration.
*   `mss`: High-performance desktop screenshots.
*   `opencv-python` & `numpy`: Computer vision template matching.
*   `pytesseract`: OCR for reading game text.
*   `evdev` & `pynput`: Direct input injection (evdev for game-level keyboard/mouse, pynput fallback).

---

## 🤝 Project Conventions & Protocols

1.  **Non-Root Execution**:
    *   The Docker container runs as host user `1000:1000` to prevent file permission mismatches on mounted directories (`./stats`).
    *   CPython toolchains and dependencies are compiled under `/opt/uv` and made globally executable (`chmod 755`).
2.  **Test-Driven Development**:
    *   All CLI expansions and helpers must have associated unit tests in `tests/`.
    *   Verify code locally before pushing:
        ```bash
        uv run pytest
        uv run ruff check
        uv run mypy .
        ```
3.  **Idempotent Schema Upgrades**:
    *   Temporal migrations are managed via a decoupled `temporal-schema-setup` job using `temporalio/admin-tools`.
    *   All database creations must be safe to re-run (e.g. `|| true` on schema initialization steps).
