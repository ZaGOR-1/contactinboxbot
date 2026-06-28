# Telegram Inbox Bot

Production-ready Telegram inbox bot with a private FastAPI web admin panel for:

```text
https://admintextbot.hotzagor.tech
```

The bot lets people message you in Telegram without knowing your personal Telegram account. Incoming messages are stored in PostgreSQL. The private web admin panel lets the single admin view users, read conversations, block users, and reply through the Telegram bot.

## Features

- Telegram bot powered by `aiogram 3`.
- Private FastAPI web admin panel.
- PostgreSQL production database.
- SQLite allowed only outside production.
- SQLAlchemy 2.x async ORM.
- Alembic migrations.
- Password-hashed admin user.
- CLI command for creating the first admin.
- Signed secure session cookies.
- CSRF-protected forms.
- Optional Telegram 2FA.
- Login brute-force protection.
- Dashboard with inbox stats.
- Messages page with search, filters, pagination, detail view, and mark-as-read.
- Users page with search, blocked filter, conversation view, reply flow, block/unblock, and mark-as-read.
- Per-user Telegram message rate limiting.
- Admin Telegram notifications for new messages.
- `/health` and `/version` service endpoints.
- Production-disabled `/docs`, `/redoc`, and `/openapi.json`.
- Nginx reverse proxy config for `admintextbot.hotzagor.tech`.
- systemd service files for web and bot processes.
- Docker Compose file for local PostgreSQL.

## Stack

- Python 3.12+
- aiogram 3
- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Jinja2
- Gunicorn + UvicornWorker or Uvicorn
- Nginx
- Let's Encrypt / Certbot
- systemd
- pydantic-settings
- passlib/bcrypt

## Telegram Bot Setup

Create the bot:

1. Open Telegram.
2. Start a chat with `@BotFather`.
3. Run `/newbot`.
4. Follow BotFather prompts.
5. Copy the token into `.env` as `TELEGRAM_BOT_TOKEN`.

Get your admin Telegram ID:

1. Message a bot such as `@userinfobot`.
2. Copy your numeric Telegram ID.
3. Put it into `.env` as `ADMIN_TELEGRAM_ID`.

Do not commit the token or admin ID in real production repositories.

## DNS

Before production deployment, create this DNS A record:

```text
admintextbot.hotzagor.tech -> VPS_PUBLIC_IP
```

The admin panel URL must be:

```text
https://admintextbot.hotzagor.tech
```

## Configuration

Copy the example env file:

```bash
cp .env.example .env
```

Replace every `CHANGE_ME` value.

Production example:

```env
APP_ENV=production
APP_NAME=Telegram Inbox Bot
APP_VERSION=1.0.0

DATABASE_URL=postgresql+asyncpg://telegram_inbox_user:CHANGE_ME@localhost:5432/telegram_inbox

TELEGRAM_BOT_TOKEN=CHANGE_ME
ADMIN_TELEGRAM_ID=CHANGE_ME

SECRET_KEY=CHANGE_ME_GENERATE_LONG_RANDOM_STRING
SESSION_COOKIE_NAME=telegram_inbox_session
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=lax

ADMIN_PANEL_BASE_URL=https://admintextbot.hotzagor.tech

ENABLE_TELEGRAM_2FA=true
ENABLE_IP_ALLOWLIST=false
ALLOWED_ADMIN_IPS=

RATE_LIMIT_MESSAGES_PER_MINUTE=5

LOG_LEVEL=INFO
```

Important:

- `.env` is ignored by Git.
- `.env.example` contains placeholders only.
- `APP_ENV=production` requires PostgreSQL.
- SQLite is allowed only outside production.
- `SECRET_KEY` must be a long random string.

## Local PostgreSQL

Start local PostgreSQL with Docker Compose:

```bash
docker compose up -d postgres
```

Use this local `DATABASE_URL`:

```env
DATABASE_URL=postgresql+asyncpg://telegram_inbox_user:CHANGE_ME_LOCAL_ONLY@localhost:5432/telegram_inbox
```

## Install Dependencies

Create and activate a virtual environment:

```bash
python -m venv .venv
. .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Check configuration:

```bash
python -c "from app.core.config import get_settings; print(get_settings().safe_summary())"
```

## Database

Create PostgreSQL database and user in production:

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE telegram_inbox;
CREATE USER telegram_inbox_user WITH PASSWORD 'CHANGE_ME';
GRANT ALL PRIVILEGES ON DATABASE telegram_inbox TO telegram_inbox_user;
\q
```

Run migrations:

```bash
alembic upgrade head
```

## First Admin

Create the first admin:

```bash
python -m app.cli.create_admin
```

The command prompts for:

- username;
- password;
- repeated password confirmation.

The password is not printed to the terminal and is stored only as a hash.

If an admin already exists, the command refuses to create another one unless you explicitly pass:

```bash
python -m app.cli.create_admin --allow-additional
```

Replace an existing admin password:

```bash
python -m app.cli.create_admin --username admin --replace-password
```

## Run Locally

Run the web admin:

```bash
uvicorn app.web.main:app --host 127.0.0.1 --port 8000
```

Run the Telegram bot:

```bash
python -m app.bot.main
```

Service checks:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/version
```

## Web Admin Usage

Open:

```text
https://admintextbot.hotzagor.tech
```

Without authorization, only the login flow is available.

After login:

- Dashboard: `/`
- Messages: `/messages`
- Users: `/users`

Messages page:

- search by text, username, Telegram ID, and name;
- filter by status, direction, and date;
- open message detail;
- mark messages as read.

Users page:

- search by name, username, and Telegram ID;
- filter blocked/not blocked users;
- open user detail;
- view conversation history;
- reply through the Telegram bot;
- block or unblock users;
- mark incoming messages as read.

## Telegram User Flow

1. A user starts the Telegram bot with `/start`.
2. The bot creates or updates the user record.
3. The user sends a text message.
4. The bot rate-limits the user.
5. The message is saved as `incoming/new`.
6. The admin receives a Telegram notification.
7. The admin opens the web admin and replies.
8. The reply is sent through the bot and saved as `outgoing`.

Unsupported files/media receive a polite fallback message.

## Production Files

Included production examples:

- `nginx/admintextbot.hotzagor.tech.conf`
- `systemd/telegram-inbox-web.service`
- `systemd/telegram-inbox-bot.service`
- `docker-compose.yml`

The web service must bind only to:

```text
127.0.0.1:8000
```

Public access should go only through Nginx HTTPS.

## Logs

Production service logs:

```bash
journalctl -u telegram-inbox-bot -f
journalctl -u telegram-inbox-web -f
systemctl status telegram-inbox-bot
systemctl status telegram-inbox-web
```

Restart services:

```bash
sudo systemctl restart telegram-inbox-bot
sudo systemctl restart telegram-inbox-web
```

## Updating

Typical update flow:

```bash
cd /opt/telegram-inbox/app
git pull
. .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart telegram-inbox-web telegram-inbox-bot
```

## Testing and Security Review

After installing dependencies, run:

```bash
python -m pytest
```

The test suite covers core security helpers, web access control, repository
flows, rate limiting, brute-force lockout, 2FA code handling, message filters,
failed replies, and admin notification formatting.

See `SECURITY_REVIEW.md` for the Phase 15 checklist, manual Telegram checks,
deployment checks, and residual risks.

## Backup and Restore

Create a backup:

```bash
pg_dump -U telegram_inbox_user -h localhost telegram_inbox > telegram_inbox_backup.sql
```

Restore a backup:

```bash
psql -U telegram_inbox_user -h localhost telegram_inbox < telegram_inbox_backup.sql
```

Store backups outside public web directories. Do not commit backups to Git.

## Security Notes

- No public registration.
- Only one admin is expected by default.
- Passwords are stored only as hashes.
- Secrets live only in `.env`.
- `.env` must never be committed.
- `TELEGRAM_BOT_TOKEN` must never be committed.
- `SECRET_KEY` must never be committed.
- Production debug is off.
- Production `/docs`, `/redoc`, and `/openapi.json` are disabled.
- Admin POST forms are CSRF-protected.
- Login has brute-force protection.
- Optional Telegram 2FA is supported.
- Cookies are `Secure`, `HttpOnly`, and `SameSite`.
- Nginx should expose only HTTPS publicly.
- Public firewall ports should be only `22`, `80`, and `443`.
- PostgreSQL must not be exposed to the internet.
- FastAPI port `8000` must not be exposed to the internet.

## Deployment

See `DEPLOY.md` for the full Ubuntu Server deployment runbook.
