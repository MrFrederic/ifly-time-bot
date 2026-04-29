# ifly-time-bot

Telegram bot for coordinating flight-time package splits ("распил"). Users create requests through a Telegram mini-app; the bot automatically matches groups whose combined hours total 10 and notifies the group chat.

## Setup

1. Create a bot via [@BotFather](https://t.me/BotFather) and obtain the token.
2. Configure a Web App for the bot in BotFather (use `/newapp` or the menu button setting) and point it to the public URL where the mini-app will be served.
3. Copy `.env.example` to `.env` and fill in the values.
4. Run with Docker Compose:

```bash
docker compose up -d --build
```

Or via Make:

```bash
make up
```

The bot container runs both the Telegram bot (polling or webhook) and a lightweight HTTP server for the mini-app on `WEBAPP_PORT` (default 8080). Put a reverse proxy (nginx / Caddy) in front to terminate TLS.

## Build and push Docker image

Use the included `Makefile` to build and push tags to Docker Hub with separate commands:

```bash
make release-latest
make release-stable
```

The Docker image build now includes the React mini-app build (TelegramUI) automatically.

You can also run steps separately:

```bash
make build-latest
make push-latest
make build-stable
make push-stable
```

To override the repository name:

```bash
make release-latest IMAGE=your-dockerhub-user/ifly-time-bot
make release-stable IMAGE=your-dockerhub-user/ifly-time-bot
```

## Local development commands

```bash
make up            # docker compose up -d --build
make logs          # follow bot logs
make down          # stop and remove containers
make build-frontend
make frontend-dev
```

`build-frontend` and `frontend-dev` use `bun` when available, otherwise `npm`.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_TOKEN` | yes | Bot token from BotFather |
| `ALLOWED_GROUP_ID` | yes | Telegram group chat ID |
| `DATABASE_URL` | yes | PostgreSQL connection string |
| `MINIAPP_URL` | yes | `t.me` deep link to the mini-app (used in dashboard button) |
| `WEBAPP_PORT` | no | Internal HTTP port for the mini-app (default `8080`) |
| `CONNECTION_MODE` | no | `polling` (default) or `webhook` |
| `WEBHOOK_URL` | no | Public URL for webhook mode |
| `PORT` | no | Webhook listen port (default `8443`) |
| `THREAD_ID` | no | Forum topic ID (default `1`) |
| `TIMEZONE` | no | IANA timezone (default `Europe/Minsk`) |
| `LOG_LEVEL` | no | Python log level (default `INFO`) |

## Commands

- `/cancel` – remove your pending request
- `/check_matches` – manually trigger the matching job
- `/start` – show help

Requests are created and edited through the mini-app button on the dashboard message in the group.
