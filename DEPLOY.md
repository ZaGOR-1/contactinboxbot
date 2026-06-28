# Ubuntu Server Deployment Guide

**Мова / Language:** [Українська](#українська) | [English](#english)

---

## Українська

Production target:

```text
https://admintextbot.hotzagor.tech
```

Цей guide описує deployment Telegram Inbox Bot на Ubuntu Server/VPS з:

- PostgreSQL, який працює локально;
- FastAPI web-адмінкою на `127.0.0.1:8000`;
- Telegram-ботом як окремим service;
- Nginx як єдиним публічним reverse proxy;
- HTTPS через Let's Encrypt / Certbot;
- systemd autostart для web і bot services.

[English version](#english)

## 1. DNS

Перед deployment створіть DNS A-запис:

```text
admintextbot.hotzagor.tech -> VPS_PUBLIC_IP
```

Дочекайтесь, поки DNS почне resolve:

```bash
dig admintextbot.hotzagor.tech
```

## 2. Встановлення пакетів

Оновіть сервер:

```bash
sudo apt update
sudo apt upgrade -y
```

Встановіть required packages:

```bash
sudo apt install -y \
  python3 \
  python3-venv \
  python3-pip \
  postgresql \
  postgresql-contrib \
  nginx \
  certbot \
  python3-certbot-nginx \
  git \
  ufw
```

Перевірте версію Python:

```bash
python3 --version
```

У production використовуйте Python 3.12+.

## 3. Linux-користувач

Створіть окремого system user:

```bash
sudo adduser --system --group --home /opt/telegram-inbox telegraminbox
```

Створіть директорію застосунку:

```bash
sudo mkdir -p /opt/telegram-inbox/app
sudo chown -R telegraminbox:telegraminbox /opt/telegram-inbox
```

## 4. Клонування проєкту

Клонуйте repository від імені окремого user:

```bash
sudo -u telegraminbox git clone YOUR_REPOSITORY_URL /opt/telegram-inbox/app
```

Перейдіть у проєкт:

```bash
cd /opt/telegram-inbox/app
```

## 5. Virtual environment

```bash
sudo -u telegraminbox python3 -m venv .venv
sudo -u telegraminbox .venv/bin/pip install --upgrade pip
sudo -u telegraminbox .venv/bin/pip install -r requirements.txt
```

## 6. PostgreSQL

Відкрийте PostgreSQL shell:

```bash
sudo -u postgres psql
```

Створіть database і user:

```sql
CREATE DATABASE telegram_inbox;
CREATE USER telegram_inbox_user WITH PASSWORD 'CHANGE_ME_STRONG_DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE telegram_inbox TO telegram_inbox_user;
\q
```

PostgreSQL має слухати тільки локально. Перевірте:

```bash
sudo ss -ltnp | grep 5432
```

Не відкривайте PostgreSQL у firewall.

## 7. Telegram bot token і admin ID

Створіть Telegram-бота:

1. Відкрийте Telegram.
2. Почніть чат із `@BotFather`.
3. Виконайте `/newbot`.
4. Скопіюйте generated token.

Знайдіть ваш admin Telegram ID:

1. Напишіть `@userinfobot` або іншому trusted ID helper.
2. Скопіюйте ваш numeric Telegram ID.

Обидва значення потрібні для `.env`.

## 8. Налаштування .env

Створіть `.env`:

```bash
sudo -u telegraminbox cp .env.example .env
sudo -u telegraminbox nano .env
```

Production `.env` має виглядати так:

```env
APP_ENV=production
APP_NAME=Telegram Inbox Bot
APP_VERSION=1.0.0

DATABASE_URL=postgresql+asyncpg://telegram_inbox_user:CHANGE_ME_STRONG_DB_PASSWORD@localhost:5432/telegram_inbox

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

Згенеруйте secret key:

```bash
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
```

Захистіть `.env`:

```bash
sudo chown telegraminbox:telegraminbox .env
sudo chmod 600 .env
```

Ніколи не комітьте `.env`.

## 9. Alembic-міграції

```bash
sudo -u telegraminbox .venv/bin/alembic upgrade head
```

Це створить:

- `users`;
- `messages`;
- `admin_users`;
- `login_attempts`;
- `two_factor_codes`;
- `settings`.

## 10. Перший адмін

Запустіть з interactive terminal:

```bash
sudo -u telegraminbox .venv/bin/python -m app.cli.create_admin
```

Команда запитає username і password. Password зберігається тільки як hash.

Якщо пізніше треба замінити password:

```bash
sudo -u telegraminbox .venv/bin/python -m app.cli.create_admin --username admin --replace-password
```

## 11. Локальний smoke test

Запустіть web-адмінку локально:

```bash
sudo -u telegraminbox .venv/bin/uvicorn app.web.main:app --host 127.0.0.1 --port 8000
```

З іншого terminal:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/version
```

Після перевірки зупиніть manual Uvicorn process.

Запустіть bot вручну:

```bash
sudo -u telegraminbox .venv/bin/python -m app.bot.main
```

Після підтвердження startup зупиніть його. Production використовує systemd.

## 12. systemd services

Скопіюйте service files:

```bash
sudo cp systemd/telegram-inbox-web.service /etc/systemd/system/telegram-inbox-web.service
sudo cp systemd/telegram-inbox-bot.service /etc/systemd/system/telegram-inbox-bot.service
sudo systemctl daemon-reload
```

Увімкніть services:

```bash
sudo systemctl enable telegram-inbox-web telegram-inbox-bot
```

Запустіть services:

```bash
sudo systemctl start telegram-inbox-web telegram-inbox-bot
```

Перевірте status:

```bash
systemctl status telegram-inbox-web
systemctl status telegram-inbox-bot
```

Web service має слухати тільки:

```text
127.0.0.1:8000
```

Перевірте:

```bash
sudo ss -ltnp | grep 8000
```

## 13. Certbot HTTPS certificate

Перед увімкненням HTTPS Nginx config випустіть certificate:

```bash
sudo mkdir -p /var/www/html
sudo certbot certonly --webroot -w /var/www/html -d admintextbot.hotzagor.tech
```

Перевірте automatic renewal:

```bash
sudo certbot renew --dry-run
```

## 14. Nginx reverse proxy

Скопіюйте config:

```bash
sudo cp nginx/admintextbot.hotzagor.tech.conf /etc/nginx/sites-available/admintextbot.hotzagor.tech.conf
```

Увімкніть site:

```bash
sudo ln -s /etc/nginx/sites-available/admintextbot.hotzagor.tech.conf /etc/nginx/sites-enabled/admintextbot.hotzagor.tech.conf
```

За потреби видаліть default site:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
```

Протестуйте й reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Config містить:

- `server_name admintextbot.hotzagor.tech`;
- HTTP to HTTPS redirect;
- proxy до `127.0.0.1:8000`;
- secure headers;
- login rate limit;
- optional Basic Auth block;
- optional IP allowlist block;
- hidden file protection.

### Optional Basic Auth

Встановіть helper:

```bash
sudo apt install -y apache2-utils
```

Створіть Basic Auth password file:

```bash
sudo htpasswd -c /etc/nginx/.telegram-inbox-admin.htpasswd admin
```

Розкоментуйте ці рядки в Nginx config:

```nginx
auth_basic "Telegram Inbox Admin";
auth_basic_user_file /etc/nginx/.telegram-inbox-admin.htpasswd;
```

Після цього:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 15. Firewall

Дозвольте тільки SSH, HTTP і HTTPS:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

Не дозволяйте:

- PostgreSQL port `5432`;
- FastAPI port `8000`.

## 16. Production verification

Відкрийте:

```text
https://admintextbot.hotzagor.tech
```

Очікувано:

- unauthenticated visitors бачать login або Basic Auth;
- після login відкривається dashboard;
- `/messages` показує messages;
- `/users` показує users;
- replies надсилаються через Telegram-бота;
- `https://admintextbot.hotzagor.tech/health` повертає `ok`;
- `/docs`, `/redoc` і `/openapi.json` недоступні у production.

Ззовні перевірте, що port `8000` не відкритий.

## 17. Логи й operations

Follow logs:

```bash
journalctl -u telegram-inbox-bot -f
journalctl -u telegram-inbox-web -f
```

Status:

```bash
systemctl status telegram-inbox-bot
systemctl status telegram-inbox-web
```

Restart:

```bash
sudo systemctl restart telegram-inbox-bot
sudo systemctl restart telegram-inbox-web
```

Reload Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 18. Оновлення після git pull

```bash
cd /opt/telegram-inbox/app
sudo -u telegraminbox git pull
sudo -u telegraminbox .venv/bin/pip install -r requirements.txt
sudo -u telegraminbox .venv/bin/alembic upgrade head
sudo systemctl restart telegram-inbox-web telegram-inbox-bot
```

Після restart перевірте logs.

## 19. Backup and restore

Створіть backup directory:

```bash
sudo mkdir -p /opt/telegram-inbox/backups
sudo chown telegraminbox:telegraminbox /opt/telegram-inbox/backups
sudo chmod 700 /opt/telegram-inbox/backups
```

Backup:

```bash
sudo -u telegraminbox pg_dump -U telegram_inbox_user -h localhost telegram_inbox > /opt/telegram-inbox/backups/telegram_inbox_$(date +%F_%H-%M).sql
```

Restore:

```bash
sudo -u telegraminbox psql -U telegram_inbox_user -h localhost telegram_inbox < /opt/telegram-inbox/backups/telegram_inbox_backup.sql
```

Не зберігайте backups у публічній web-директорії.
Не комітьте backups у Git.

## 20. Локальний PostgreSQL через Docker Compose

Для local development:

```bash
docker compose up -d postgres
```

Використайте:

```env
DATABASE_URL=postgresql+asyncpg://telegram_inbox_user:CHANGE_ME_LOCAL_ONLY@localhost:5432/telegram_inbox
```

Compose file прив'язує PostgreSQL до:

```text
127.0.0.1:5432
```

## 21. Security checklist

- `.env` існує і має mode `600`.
- `.env` не закомічений у Git.
- Реальний Telegram token не закомічений.
- Реальний `SECRET_KEY` не закомічений.
- PostgreSQL слухає тільки локально.
- FastAPI слухає `127.0.0.1:8000`.
- Firewall відкриває тільки `22`, `80`, `443`.
- Nginx terminates HTTPS.
- Certbot renewal test проходить.
- `/docs`, `/redoc` і `/openapi.json` вимкнені у production.
- Admin login працює.
- Optional Telegram 2FA працює, якщо enabled.
- systemd services restart on failure.
- Logs не показують passwords, tokens або session cookies.

[English version](#english) | [До початку](#ubuntu-server-deployment-guide)

---

## English

Production target:

```text
https://admintextbot.hotzagor.tech
```

This guide deploys Telegram Inbox Bot on Ubuntu Server/VPS with:

- PostgreSQL running locally;
- FastAPI web admin on `127.0.0.1:8000`;
- Telegram bot as a separate service;
- Nginx as the only public reverse proxy;
- HTTPS through Let's Encrypt / Certbot;
- systemd autostart for both web and bot services.

[Українська версія](#українська)

## 1. DNS

Create this DNS A record before deployment:

```text
admintextbot.hotzagor.tech -> VPS_PUBLIC_IP
```

Wait until DNS resolves:

```bash
dig admintextbot.hotzagor.tech
```

## 2. Install Packages

Update the server:

```bash
sudo apt update
sudo apt upgrade -y
```

Install required packages:

```bash
sudo apt install -y \
  python3 \
  python3-venv \
  python3-pip \
  postgresql \
  postgresql-contrib \
  nginx \
  certbot \
  python3-certbot-nginx \
  git \
  ufw
```

Confirm Python version:

```bash
python3 --version
```

Use Python 3.12+ in production.

## 3. Create Linux User

Create a dedicated system user:

```bash
sudo adduser --system --group --home /opt/telegram-inbox telegraminbox
```

Create application directory:

```bash
sudo mkdir -p /opt/telegram-inbox/app
sudo chown -R telegraminbox:telegraminbox /opt/telegram-inbox
```

## 4. Clone Project

Clone the repository as the dedicated user:

```bash
sudo -u telegraminbox git clone YOUR_REPOSITORY_URL /opt/telegram-inbox/app
```

Enter the project:

```bash
cd /opt/telegram-inbox/app
```

## 5. Create Virtual Environment

```bash
sudo -u telegraminbox python3 -m venv .venv
sudo -u telegraminbox .venv/bin/pip install --upgrade pip
sudo -u telegraminbox .venv/bin/pip install -r requirements.txt
```

## 6. PostgreSQL

Open PostgreSQL shell:

```bash
sudo -u postgres psql
```

Create database and user:

```sql
CREATE DATABASE telegram_inbox;
CREATE USER telegram_inbox_user WITH PASSWORD 'CHANGE_ME_STRONG_DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE telegram_inbox TO telegram_inbox_user;
\q
```

PostgreSQL must listen locally only. Check:

```bash
sudo ss -ltnp | grep 5432
```

Do not open PostgreSQL in the firewall.

## 7. Telegram Bot Token and Admin ID

Create a Telegram bot:

1. Open Telegram.
2. Start `@BotFather`.
3. Run `/newbot`.
4. Copy the generated token.

Find your admin Telegram ID:

1. Message `@userinfobot` or another trusted ID helper.
2. Copy your numeric Telegram ID.

You need both values for `.env`.

## 8. Configure .env

Create `.env`:

```bash
sudo -u telegraminbox cp .env.example .env
sudo -u telegraminbox nano .env
```

Production `.env` should look like:

```env
APP_ENV=production
APP_NAME=Telegram Inbox Bot
APP_VERSION=1.0.0

DATABASE_URL=postgresql+asyncpg://telegram_inbox_user:CHANGE_ME_STRONG_DB_PASSWORD@localhost:5432/telegram_inbox

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

Generate a secret key:

```bash
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
```

Secure `.env`:

```bash
sudo chown telegraminbox:telegraminbox .env
sudo chmod 600 .env
```

Never commit `.env`.

## 9. Run Alembic Migrations

```bash
sudo -u telegraminbox .venv/bin/alembic upgrade head
```

This creates:

- `users`;
- `messages`;
- `admin_users`;
- `login_attempts`;
- `two_factor_codes`;
- `settings`.

## 10. Create First Admin

Run from an interactive terminal:

```bash
sudo -u telegraminbox .venv/bin/python -m app.cli.create_admin
```

The command asks for username and password. The password is stored only as a hash.

If you need to replace the password later:

```bash
sudo -u telegraminbox .venv/bin/python -m app.cli.create_admin --username admin --replace-password
```

## 11. Local Smoke Test

Run web admin locally:

```bash
sudo -u telegraminbox .venv/bin/uvicorn app.web.main:app --host 127.0.0.1 --port 8000
```

From another terminal:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/version
```

Stop the manual Uvicorn process after the check.

Run bot manually:

```bash
sudo -u telegraminbox .venv/bin/python -m app.bot.main
```

Stop it after confirming startup. Production uses systemd.

## 12. systemd Services

Copy service files:

```bash
sudo cp systemd/telegram-inbox-web.service /etc/systemd/system/telegram-inbox-web.service
sudo cp systemd/telegram-inbox-bot.service /etc/systemd/system/telegram-inbox-bot.service
sudo systemctl daemon-reload
```

Enable services:

```bash
sudo systemctl enable telegram-inbox-web telegram-inbox-bot
```

Start services:

```bash
sudo systemctl start telegram-inbox-web telegram-inbox-bot
```

Check status:

```bash
systemctl status telegram-inbox-web
systemctl status telegram-inbox-bot
```

The web service must listen only on:

```text
127.0.0.1:8000
```

Check:

```bash
sudo ss -ltnp | grep 8000
```

## 13. Certbot HTTPS Certificate

Before enabling the HTTPS Nginx config, issue the certificate:

```bash
sudo mkdir -p /var/www/html
sudo certbot certonly --webroot -w /var/www/html -d admintextbot.hotzagor.tech
```

Check automatic renewal:

```bash
sudo certbot renew --dry-run
```

## 14. Nginx Reverse Proxy

Copy config:

```bash
sudo cp nginx/admintextbot.hotzagor.tech.conf /etc/nginx/sites-available/admintextbot.hotzagor.tech.conf
```

Enable site:

```bash
sudo ln -s /etc/nginx/sites-available/admintextbot.hotzagor.tech.conf /etc/nginx/sites-enabled/admintextbot.hotzagor.tech.conf
```

Remove default site if needed:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
```

Test and reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

The config includes:

- `server_name admintextbot.hotzagor.tech`;
- HTTP to HTTPS redirect;
- proxy to `127.0.0.1:8000`;
- secure headers;
- login rate limit;
- optional Basic Auth block;
- optional IP allowlist block;
- hidden file protection.

### Optional Basic Auth

Install helper:

```bash
sudo apt install -y apache2-utils
```

Create Basic Auth password file:

```bash
sudo htpasswd -c /etc/nginx/.telegram-inbox-admin.htpasswd admin
```

Uncomment these lines in the Nginx config:

```nginx
auth_basic "Telegram Inbox Admin";
auth_basic_user_file /etc/nginx/.telegram-inbox-admin.htpasswd;
```

Then:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 15. Firewall

Allow only SSH, HTTP, and HTTPS:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

Do not allow:

- PostgreSQL port `5432`;
- FastAPI port `8000`.

## 16. Verify Production

Open:

```text
https://admintextbot.hotzagor.tech
```

Expected:

- unauthenticated visitors see login or Basic Auth;
- after login, dashboard opens;
- `/messages` shows messages;
- `/users` shows users;
- replies are sent through the Telegram bot;
- `https://admintextbot.hotzagor.tech/health` returns `ok`;
- `/docs`, `/redoc`, and `/openapi.json` are unavailable in production.

Check externally that port `8000` is not open.

## 17. Logs and Operations

Follow logs:

```bash
journalctl -u telegram-inbox-bot -f
journalctl -u telegram-inbox-web -f
```

Status:

```bash
systemctl status telegram-inbox-bot
systemctl status telegram-inbox-web
```

Restart:

```bash
sudo systemctl restart telegram-inbox-bot
sudo systemctl restart telegram-inbox-web
```

Reload Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 18. Update After git pull

```bash
cd /opt/telegram-inbox/app
sudo -u telegraminbox git pull
sudo -u telegraminbox .venv/bin/pip install -r requirements.txt
sudo -u telegraminbox .venv/bin/alembic upgrade head
sudo systemctl restart telegram-inbox-web telegram-inbox-bot
```

Check logs after restart.

## 19. Backup and Restore

Create backup directory:

```bash
sudo mkdir -p /opt/telegram-inbox/backups
sudo chown telegraminbox:telegraminbox /opt/telegram-inbox/backups
sudo chmod 700 /opt/telegram-inbox/backups
```

Backup:

```bash
sudo -u telegraminbox pg_dump -U telegram_inbox_user -h localhost telegram_inbox > /opt/telegram-inbox/backups/telegram_inbox_$(date +%F_%H-%M).sql
```

Restore:

```bash
sudo -u telegraminbox psql -U telegram_inbox_user -h localhost telegram_inbox < /opt/telegram-inbox/backups/telegram_inbox_backup.sql
```

Do not store backups in a public web directory.
Do not commit backups to Git.

## 20. Local PostgreSQL with Docker Compose

For local development:

```bash
docker compose up -d postgres
```

Use:

```env
DATABASE_URL=postgresql+asyncpg://telegram_inbox_user:CHANGE_ME_LOCAL_ONLY@localhost:5432/telegram_inbox
```

The Compose file binds PostgreSQL to:

```text
127.0.0.1:5432
```

## 21. Security Checklist

- `.env` exists and has mode `600`.
- `.env` is not committed to Git.
- Real Telegram token is not committed.
- Real `SECRET_KEY` is not committed.
- PostgreSQL listens locally only.
- FastAPI listens on `127.0.0.1:8000`.
- Firewall exposes only `22`, `80`, `443`.
- Nginx terminates HTTPS.
- Certbot renewal test passes.
- `/docs`, `/redoc`, and `/openapi.json` are disabled in production.
- Admin login works.
- Optional Telegram 2FA works if enabled.
- systemd services restart on failure.
- Logs do not expose passwords, tokens, or session cookies.

[Українська версія](#українська) | [Back to top](#ubuntu-server-deployment-guide)
