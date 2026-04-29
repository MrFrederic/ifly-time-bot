# Copilot Instructions for ifly-time-bot

## Architecture
- This is a **single Python process** that runs both:
  - Telegram bot (python-telegram-bot)
  - FastAPI mini-app backend + static frontend
- Entry point is `src/main.py`: initializes DB, builds Telegram `Application`, registers handlers/jobs, then starts Uvicorn for the webapp.
- Bot and webapp share runtime state through `src/webapp/app.py` (`create_app(application)` stores the bot `Application` globally for route dependencies).

## Request flow
- Users create/edit/cancel requests via Telegram WebApp UI (`src/webapp/static/index.html`) -> API routes (`src/webapp/routes.py`).
- API routes validate Telegram `initData` from `Authorization: tma ...` (`src/webapp/auth.py`) and resolve `user_id`.
- Requests are stored in PostgreSQL via SQLAlchemy model `Request` (`src/database.py`).
- After POST/DELETE in routes, code always:
  1. invalidates request list cache (`invalidate_request_cache`)
  2. runs matching (`check_matches_and_notify` for save)
  3. refreshes sticky dashboard message (`refresh_sticky_list`)

## Matching + sticky behavior
- Matching target is fixed at **10 hours**; algorithm tries group sizes **4 -> 3 -> 2**, using FIFO candidate order (`src/matching.py`).
- Candidates are pending requests with `target_date <= today` (timezone-aware via `settings.tz`).
- Sticky message persistence is DB-backed (`BotState` keys `sticky_list_message_id`/`sticky_list_content`) in `src/handlers/sticky.py`.
- `refresh_sticky_list` semantics are intentional:
  - `is_system=True`: edit/skip when unchanged
  - `is_system=False`: resend to keep dashboard at chat bottom
- Any feature that changes pending requests should preserve this refresh contract.

## Chat/thread conventions
- Bot actions are constrained to configured group/topic: `check_group` validates both `ALLOWED_GROUP_ID` and `THREAD_ID` (`src/helpers.py`).
- Command handlers usually delete user command message (`delete_command_message`) and send bot response into configured thread.
- Keep user-facing text in `src/messages.py` (Russian copy is expected by current UX).

## Runtime workflow
- Configuration is from `.env` via Pydantic Settings (`src/config.py`); required vars include `TELEGRAM_TOKEN`, `ALLOWED_GROUP_ID`, `DATABASE_URL`, `MINIAPP_URL`.
- Local/container run path is Docker-first:
  - `docker compose up -d --build`
- Connection modes:
  - `polling` (default)
  - `webhook` requires `WEBHOOK_URL` and `PORT`

## Change guidelines for AI agents
- Prefer minimal, flow-safe changes around these hotspots:
  - `src/webapp/routes.py` for request lifecycle
  - `src/matching.py` for grouping logic
  - `src/handlers/sticky.py` and `src/helpers.py` for dashboard/list behavior
- Preserve timezone-aware date handling (`datetime.now(settings.tz)`) and 0.5-hour increments enforced by API/frontend.
- There is currently no dedicated test suite in repo; validate changes by running the bot/webapp flow and checking logs.
