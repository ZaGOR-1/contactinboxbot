# Security Review

This review maps the Phase 15 checklist from `plan.md` to concrete automated
checks, manual deployment checks, and known residual risks.

## Automated Checks

Run after installing dependencies:

```bash
python -m pytest
```

The test suite covers:

- password hashing does not store plaintext passwords;
- signed sessions reject tampering and expire;
- pending 2FA cookies are signed and expire;
- CSRF token/digest validation rejects missing or mismatched tokens;
- session, CSRF, and pending 2FA cookies use `Secure`, `HttpOnly`, and `SameSite`;
- `.env` is ignored and `.env.example` contains placeholders only;
- unauthenticated admin routes are blocked;
- unsafe POST routes are blocked without session/CSRF;
- `/docs`, `/redoc`, and `/openapi.json` are disabled in production;
- `/health` returns successfully and security headers are present;
- user upsert, message creation, search/filter, mark-as-read, block filters;
- rate limit blocks after the configured message count;
- login brute-force lockout triggers after 5 failed attempts from one IP;
- 2FA codes are hashed, expiring, and single-use;
- failed Telegram replies are persisted as outgoing `failed` messages;
- admin notifications include the user conversation link.

## Manual Functional Checks

These require a real Telegram bot token and a reachable production-like server:

1. Send `/start` to the bot and confirm the user is created or updated.
2. Send a text message and confirm it appears in `/messages`.
3. Confirm the admin receives a Telegram notification.
4. Reply from `/users/{id}` and confirm the user receives the message.
5. Temporarily break Telegram delivery and confirm an outgoing `failed` row is saved.
6. Block a user and confirm new messages are rejected by the bot.
7. Exercise `/messages` search and filters together.
8. Exercise `/users` search and blocked/active filters together.
9. Mark a message or user conversation as read.
10. Log out and confirm protected pages return `403` until login.

## Manual Deployment Checks

Run on Ubuntu Server after deployment:

```bash
systemctl status telegram-inbox-web
systemctl status telegram-inbox-bot
curl http://127.0.0.1:8000/health
curl -I https://admintextbot.hotzagor.tech
sudo nginx -t
sudo certbot renew --dry-run
sudo ufw status
```

Confirm:

- DNS A record points `admintextbot.hotzagor.tech` to the VPS IP;
- Certbot certificate exists for `admintextbot.hotzagor.tech`;
- port `8000` is not exposed publicly;
- only `22`, `80`, and `443` are open in the firewall;
- PostgreSQL listens locally only;
- Nginx blocks `.env`, `.git`, and hidden files;
- production `/docs`, `/redoc`, and `/openapi.json` are unavailable.

## Residual Risks

- Telegram delivery can fail because of token revocation, user privacy settings,
  network errors, or Telegram API outages. Failed admin replies are persisted with
  `status=failed`; admin notification failures are logged.
- IP-based brute-force protection depends on correct reverse proxy forwarding.
  Nginx must preserve `X-Forwarded-For` and only trusted proxy traffic should
  reach the FastAPI service.
- The optional IP allowlist is exact-match only. If admin IPs are dynamic, keep it
  disabled or update `ALLOWED_ADMIN_IPS` before enabling.
- Backups contain private user messages. Store them outside public web roots,
  never commit them, and protect them with filesystem permissions or external
  storage encryption.
- If Basic Auth is enabled in Nginx, rotate its credentials separately from the
  application admin password.
