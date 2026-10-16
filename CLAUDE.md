# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Home Assistant custom integration (domain `pendel`) for the Pendel work time tracker (separate repo `Schally0711/pendel`, backend API under `/api`). HACS-compatible layout: `custom_components/pendel/` at the repo root, `hacs.json`.

## Commands

```bash
.venv/bin/pytest                                   # all tests (pytest-homeassistant-custom-component, real HA core)
.venv/bin/pytest tests/test_init.py::test_sensors  # single test
.venv/bin/ruff check . && .venv/bin/ruff format .
```

The `pytest-homeassistant-custom-component` version pins the HA version; keep it in line with the HA release being targeted.

## Architecture

- `config_flow.py` – step `user` exchanges e-mail/password for an API token via `POST /api/auth/token` (password never stored), step `tracking` picks person + home/office zone entities and writes them to Pendel's places (`Place.zone` = zone entity id; Pendel matches zones case-insensitively without the `zone.` prefix). Options flow edits the tracking settings; reauth creates a new token. Unique id = `<url>#<pendel user id>`.
- `tracker.py` – listens to the person's state, maps states to the configured zone entity ids (anything else → `not_home`), skips no-op changes and posts `zone_change` events. Unsent events are kept in a `Store` (`pendel.<entry_id>.queue`) and retried every minute; events older than 7 days are dropped (Pendel would reject them).
- `coordinator.py` – polls `/api/today`, `/api/vacation/<year>`, `/api/absences?year=` every 60 s; derives `status` and the next absence. 401 → `ConfigEntryAuthFailed` (reauth).
- `sensor.py` / `button.py` – entity descriptions; durations are reported in minutes with suggested unit hours. Buttons call `/api/clock/*`; 404/409/422 from Pendel become translated `HomeAssistantError`s.
- `brand/icon.png` (256 px) and `icon@2x.png` (512 px): local brand images (HA ≥ 2026.3, also used by HACS), rendered from Pendel's `frontend/assets/icon.svg`.
- Releases: tag `v<manifest version>` → `release.yml` publishes a GitHub release with `pendel.zip`.
- Translations: `strings.json` (= `translations/en.json`) and `translations/de.json` must stay in sync; entity names come from `translation_key`.

The state-machine logic (what a zone change means) lives in Pendel (`backend/pendel/automation.py`), not here.
