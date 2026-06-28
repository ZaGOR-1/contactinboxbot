# План реалізації Telegram Inbox Bot

Цей план побудований на основі вимог із `promt.md` і розбиває розробку production-ready Telegram Inbox Bot на послідовні фази. Мета: отримати повністю робочий застосунок для Ubuntu Server/VPS з Telegram-ботом, закритою веб-адмінкою на `https://admintextbot.hotzagor.tech`, PostgreSQL, HTTPS, systemd, Nginx і багаторівневим захистом доступу.

## 0. Основні принципи реалізації

- Проєкт не є демо або заглушкою: кожна фаза має завершуватися робочим інкрементом.
- Секрети, токени, паролі та приватні ключі зберігаються тільки в `.env`.
- У production назовні відкриті тільки порти `22`, `80`, `443`.
- FastAPI слухає тільки `127.0.0.1:8000`.
- PostgreSQL працює локально і не відкривається в інтернет.
- Адмінка повністю закрита: без авторизації недоступна жодна сторінка, крім login/2FA.
- Публічної реєстрації немає.
- За замовчуванням існує тільки один адмін, який створюється через CLI.
- У production вимкнені `debug`, відкриті `/docs` і `/redoc`.
- Всі POST-дії в адмінці перевіряють авторизацію та CSRF-захист.
- Логи не містять паролів, токенів або session cookies.

## 1. Цільова архітектура

### Компоненти

- Telegram bot service:
  - окремий процес;
  - запускається через `systemd`;
  - використовує `aiogram 3`;
  - приймає повідомлення користувачів;
  - зберігає повідомлення в базу;
  - надсилає адміну Telegram-сповіщення.

- Web admin service:
  - окремий процес;
  - запускається через `systemd`;
  - використовує `FastAPI`, `Jinja2`, `SQLAlchemy 2.x`;
  - слухає тільки `127.0.0.1:8000`;
  - доступний назовні тільки через Nginx і HTTPS.

- Database:
  - PostgreSQL для production;
  - SQLite дозволений тільки для локального dev-режиму;
  - міграції через Alembic.

- Reverse proxy:
  - Nginx;
  - `server_name admintextbot.hotzagor.tech`;
  - HTTPS через Let's Encrypt / Certbot;
  - secure headers;
  - optional Basic Auth;
  - optional IP allowlist;
  - login rate limit.

### Production flow

1. Користувач пише Telegram-боту.
2. Бот створює або оновлює користувача в базі.
3. Бот зберігає incoming message зі статусом `new`.
4. Бот надсилає адміну сповіщення з посиланням на профіль користувача в адмінці.
5. Адмін входить на `https://admintextbot.hotzagor.tech`.
6. Адмін читає переписку і відповідає з веб-адмінки.
7. Web service надсилає відповідь через Telegram Bot API.
8. Відповідь зберігається як outgoing message.
9. Incoming messages позначаються як `answered` або `read`.

## 2. Структура проєкту

Цільова структура:

```text
project/
app/
  bot/
    main.py
    handlers.py
    middlewares.py
    keyboards.py
  web/
    main.py
    routes/
      auth.py
      dashboard.py
      messages.py
      users.py
      settings.py
    templates/
      base.html
      login.html
      two_factor.html
      dashboard.html
      messages.html
      users.html
      user_detail.html
      errors/
        403.html
        404.html
        500.html
    static/
      css/
        style.css
      js/
        app.js
  core/
    config.py
    security.py
    logging.py
    permissions.py
  db/
    database.py
    models.py
    repositories.py
  services/
    telegram_service.py
    message_service.py
    user_service.py
    auth_service.py
    rate_limit_service.py
    two_factor_service.py
  cli/
    create_admin.py
alembic/
alembic.ini
requirements.txt
.env.example
.gitignore
README.md
DEPLOY.md
docker-compose.yml
nginx/
  admintextbot.hotzagor.tech.conf
systemd/
  telegram-inbox-bot.service
  telegram-inbox-web.service
```

## 3. Фаза 1: Ініціалізація проєкту

### Завдання

- Створити базову структуру директорій.
- Додати `requirements.txt`.
- Додати `.gitignore`.
- Додати `.env.example` з усіма required-змінними.
- Додати базовий `README.md`.
- Додати базовий `DEPLOY.md`.
- Налаштувати `pydantic-settings` або `python-dotenv`.
- Створити `app/core/config.py`.
- Створити `app/core/logging.py`.
- Додати розділення `dev` і `production` через `APP_ENV`.

### Обов'язкові env-змінні

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

### Критерії готовності

- Проєкт імпортується без помилок.
- Конфіг читається з `.env`.
- `.env` не потрапляє в Git.
- `.env.example` не містить реальних секретів.
- Логування працює і не виводить секрети.

## 4. Фаза 2: База даних і міграції

### Завдання

- Налаштувати async SQLAlchemy 2.x.
- Додати `app/db/database.py`.
- Описати моделі в `app/db/models.py`.
- Налаштувати Alembic.
- Створити першу міграцію.
- Додати repository layer для базових операцій.
- Перевірити роботу з PostgreSQL.
- Дозволити SQLite тільки для локального dev-режиму.

### Моделі

#### User

- `id`
- `telegram_id`, unique, indexed
- `username`, nullable, indexed
- `first_name`, nullable
- `last_name`, nullable
- `language_code`, nullable
- `is_blocked`, default false
- `created_at`
- `updated_at`
- `last_message_at`

#### Message

- `id`
- `user_id`, foreign key
- `direction`: `incoming` або `outgoing`
- `text`
- `status`: `new`, `read`, `answered`, `failed`
- `telegram_message_id`, nullable
- `error_text`, nullable
- `created_at`

#### AdminUser

- `id`
- `username`, unique
- `password_hash`
- `is_active`
- `created_at`
- `updated_at`
- `last_login_at`

#### LoginAttempt

- `id`
- `ip_address`
- `username`
- `success`
- `created_at`

#### TwoFactorCode

- `id`
- `admin_user_id`
- `code_hash`
- `expires_at`
- `used_at`
- `created_at`

#### Settings

- `id`
- `key`
- `value`

### Критерії готовності

- `alembic upgrade head` створює всі таблиці.
- Унікальні індекси і foreign keys працюють.
- `telegram_id` і `username` індексовані.
- Timestamps створюються коректно.
- Можна підключитися до PostgreSQL через `DATABASE_URL`.

## 5. Фаза 3: Core security layer

### Завдання

- Додати `app/core/security.py`.
- Додати хешування паролів через `passlib/bcrypt` або `argon2`.
- Додати генерацію і перевірку CSRF-токенів.
- Додати signed cookie або server-side sessions.
- Додати secure cookie settings:
  - `Secure`;
  - `HttpOnly`;
  - `SameSite=Lax`.
- Додати `app/core/permissions.py`.
- Додати dependency/helper для перевірки authenticated admin.
- Додати graceful error pages: `403`, `404`, `500`.
- Заборонити відкриті `/docs` і `/redoc` у production.

### Критерії готовності

- Паролі не зберігаються відкритим текстом.
- CSRF перевіряється для POST-форм.
- Без сесії неможливо відкрити `/`, `/users`, `/messages`.
- У production немає публічних `/docs` і `/redoc`.
- Stack trace не показується в браузері.

## 6. Фаза 4: CLI для створення першого адміна

### Завдання

- Реалізувати `python -m app.cli.create_admin`.
- Запитувати `username`.
- Запитувати `password` без виводу в консоль.
- Просити повторити password.
- Перевіряти збіг паролів.
- Хешувати пароль.
- Створювати першого адміна.
- Якщо адмін уже існує, не створювати другого без явного прапорця.
- Додати опційний прапорець для force/replace або allow additional admin, якщо буде потрібно.

### Критерії готовності

- CLI створює першого адміна.
- Пароль не видно в терміналі.
- Password hash записується в базу.
- Повторний запуск без прапорця не створює другого адміна.

## 7. Фаза 5: Telegram bot MVP

### Завдання

- Створити `app/bot/main.py`.
- Налаштувати `aiogram 3`.
- Створити `app/bot/handlers.py`.
- Реалізувати `/start`.
- Зберігати або оновлювати користувача:
  - `telegram_id`;
  - `username`;
  - `first_name`;
  - `last_name`;
  - `language_code`;
  - `created_at`;
  - `updated_at`;
  - `last_message_at`.
- Приймати текстові повідомлення.
- Зберігати incoming messages зі статусом `new`.
- Не приймати повідомлення від blocked users.
- Коректно відповідати на unsupported attachments.
- Не допускати падіння бота через непідтримуваний тип повідомлення.

### Критерії готовності

- `/start` працює.
- Текстові повідомлення зберігаються в базу.
- Заблокований користувач не може надсилати повідомлення.
- Непідтримувані вкладення не ламають бота.

## 8. Фаза 6: Rate limit і Telegram-сповіщення адміну

### Завдання

- Реалізувати `app/services/rate_limit_service.py`.
- Додати ліміт повідомлень на користувача:
  - default `5` повідомлень за хвилину;
  - значення береться з `RATE_LIMIT_MESSAGES_PER_MINUTE`.
- Логувати перевищення ліміту.
- Реалізувати `app/services/telegram_service.py`.
- Надсилати адміну сповіщення про нове повідомлення.
- У сповіщенні показувати:
  - ім'я користувача;
  - username, якщо є;
  - telegram_id;
  - текст повідомлення;
  - дату і час;
  - посилання на сторінку користувача в адмінці.

### Критерії готовності

- Після нового повідомлення адмін отримує Telegram notification.
- Посилання веде на `https://admintextbot.hotzagor.tech/users/{id}`.
- Rate limit блокує спам і просить користувача зачекати.
- Події rate limit записуються в лог.

## 9. Фаза 7: Web admin auth

### Завдання

- Створити `app/web/main.py`.
- Підключити Jinja2 templates і static files.
- Реалізувати routes:
  - `GET /login`;
  - `POST /login`;
  - `GET /2fa`;
  - `POST /2fa`;
  - `POST /logout`.
- Реалізувати login/password auth.
- Реалізувати brute-force protection:
  - після 5 неправильних спроб тимчасово блокувати login з IP.
- Реалізувати optional Telegram 2FA:
  - після login/password бот надсилає код на `ADMIN_TELEGRAM_ID`;
  - код діє 5 хвилин;
  - код зберігається тільки як hash;
  - використаний код не можна використати повторно.
- Додати logout.
- Додати flash messages для помилок і успіху.

### Критерії готовності

- Неавторизований користувач бачить тільки login/2FA.
- Успішний login створює захищену сесію.
- Logout видаляє сесію.
- Brute-force protection блокує підозрілі спроби.
- Optional Telegram 2FA працює, якщо `ENABLE_TELEGRAM_2FA=true`.

## 10. Фаза 8: Dashboard

### Завдання

- Реалізувати `GET /`.
- Створити `dashboard.html`.
- Показати:
  - загальну кількість користувачів;
  - загальну кількість повідомлень;
  - кількість нових повідомлень;
  - кількість заблокованих користувачів;
  - останні 10 повідомлень;
  - швидке посилання на непрочитані повідомлення.
- Додати навігацію в `base.html`.

### Критерії готовності

- Dashboard доступний тільки після login.
- Статистика рахується з бази.
- Останні повідомлення мають посилання на користувача або деталі повідомлення.
- Непрочитані повідомлення виділяються візуально.

## 11. Фаза 9: Messages section

### Завдання

- Реалізувати routes:
  - `GET /messages`;
  - `GET /messages/{id}`;
  - `POST /messages/{id}/read`.
- Створити `messages.html`.
- Додати таблицю повідомлень з полями:
  - ID;
  - дата;
  - користувач;
  - username;
  - telegram_id;
  - текст;
  - direction;
  - status;
  - кнопка "Відкрити".
- Додати пошук по:
  - тексту;
  - username;
  - telegram_id;
  - імені.
- Додати фільтри:
  - `new`;
  - `read`;
  - `answered`;
  - `failed`;
  - `incoming`;
  - `outgoing`;
  - дата.
- Додати пагінацію.

### Критерії готовності

- Сторінка повідомлень доступна тільки після login.
- Пошук і фільтри можна комбінувати.
- Довгі повідомлення обрізаються в таблиці.
- Повний текст доступний на сторінці перегляду.
- POST read захищений CSRF і авторизацією.

## 12. Фаза 10: Users section і сторінка переписки

### Завдання

- Реалізувати routes:
  - `GET /users`;
  - `GET /users/{id}`;
  - `POST /users/{id}/reply`;
  - `POST /users/{id}/block`;
  - `POST /users/{id}/unblock`.
- Створити `users.html`.
- Створити `user_detail.html`.
- На сторінці users показати:
  - ім'я;
  - username;
  - telegram_id;
  - кількість повідомлень;
  - дата останнього повідомлення;
  - статус blocked/not blocked.
- Додати пошук.
- Додати фільтр заблокованих.
- На сторінці конкретного користувача показати:
  - telegram_id;
  - username;
  - first_name;
  - last_name;
  - language_code;
  - created_at;
  - updated_at;
  - last_message_at;
  - is_blocked.
- Показати історію переписки у вигляді чату.
- Виділяти непрочитані повідомлення.
- Додати форму відповіді.
- Додати кнопки:
  - "Позначити як прочитане";
  - "Заблокувати";
  - "Розблокувати".

### Логіка reply

1. Перевірити авторизацію і CSRF.
2. Перевірити, що користувач існує.
3. Перевірити, що користувач не заблокований.
4. Надіслати повідомлення через Telegram Bot API.
5. Якщо Telegram повернув success:
   - створити outgoing message зі статусом `answered`;
   - зберегти `telegram_message_id`;
   - incoming messages користувача позначити як `answered` або `read`.
6. Якщо Telegram повернув error:
   - створити outgoing message зі статусом `failed`;
   - записати `error_text`;
   - показати помилку в адмінці.

### Критерії готовності

- Адмін може переглядати переписку.
- Адмін може відповідати користувачу через бота.
- Telegram errors не ламають адмінку.
- Block/unblock працює.
- Заблокований користувач не може надсилати нові повідомлення.

## 13. Фаза 11: UX і frontend polish

### Завдання

- Реалізувати `base.html` з чистою навігацією.
- Використати Bootstrap 5 або сучасний чистий CSS.
- Додати `app/web/static/css/style.css`.
- Додати `app/web/static/js/app.js`, якщо потрібна мінімальна інтерактивність.
- Зробити responsive layout для desktop і mobile.
- Візуально виділяти unread/new messages.
- Обрізати довгі повідомлення в таблицях.
- Додати зрозумілі success/error alerts.
- Додати graceful empty states для порожніх списків.

### Критерії готовності

- Адмінка зручна на ПК.
- Адмінка нормально відкривається з телефона.
- Текст не ламає таблиці.
- Кнопки і форми мають зрозумілі стани.
- Немає сторінок без навігації, крім login/2FA/error pages.

## 14. Фаза 12: Service endpoints і production behavior

### Завдання

- Додати:
  - `GET /health`;
  - `GET /version`.
- Налаштувати production error handling.
- Додати заголовок `X-Robots-Tag: noindex, nofollow`.
- Перевірити, що stack traces не показуються в browser.
- Перевірити, що секрети не потрапляють у logs.
- Перевірити, що `/docs` і `/redoc` вимкнені в production.

### Критерії готовності

- `/health` повертає статус застосунку.
- `/version` повертає версію з конфігу.
- Production behavior відрізняється від dev behavior.
- Неавторизований доступ до admin routes повертає redirect/login або `403`.

## 15. Фаза 13: Nginx, systemd, Docker Compose

### Завдання

- Створити `nginx/admintextbot.hotzagor.tech.conf`.
- Налаштувати:
  - `server_name admintextbot.hotzagor.tech`;
  - `proxy_pass http://127.0.0.1:8000`;
  - HTTPS-ready конфіг;
  - secure headers;
  - `client_max_body_size`;
  - rate limit для login;
  - optional Basic Auth;
  - optional IP allowlist;
  - `X-Robots-Tag noindex, nofollow`;
  - блокування доступу до `.env`, `.git`, hidden files.
- Створити `systemd/telegram-inbox-bot.service`.
- Створити `systemd/telegram-inbox-web.service`.
- Додати `docker-compose.yml` для локального PostgreSQL.

### systemd web service

- Запуск FastAPI через `uvicorn` або `gunicorn` + `UvicornWorker`.
- Робота від Linux-користувача `telegraminbox`.
- `Restart=on-failure`.
- `EnvironmentFile` вказує на production `.env`.
- Автозапуск після reboot.

### systemd bot service

- Запуск `app.bot.main`.
- Робота від Linux-користувача `telegraminbox`.
- `Restart=on-failure`.
- `EnvironmentFile` вказує на production `.env`.
- Автозапуск після reboot.

### Критерії готовності

- Конфіги можна скопіювати на Ubuntu Server.
- Web service слухає тільки localhost.
- Bot service стартує окремо від web service.
- Nginx не відкриває напряму `.env`, `.git` або інші hidden files.

## 16. Фаза 14: Документація

### README.md

README має містити:

- опис проєкту;
- як створити Telegram-бота через BotFather;
- як отримати `TELEGRAM_BOT_TOKEN`;
- як дізнатися свій `ADMIN_TELEGRAM_ID`;
- як підготувати сервер;
- як налаштувати DNS A-запис для `admintextbot.hotzagor.tech`;
- як налаштувати `.env`;
- як встановити залежності;
- як створити базу PostgreSQL;
- як запустити міграції;
- як створити першого адміна;
- як запустити бота;
- як запустити веб-адмінку;
- як увійти в адмінку;
- як відповідати користувачам;
- як блокувати користувачів;
- як дивитися логи;
- як перезапускати сервіси;
- як оновлювати проєкт;
- як робити backup бази даних.

### DEPLOY.md

DEPLOY має містити повну інструкцію для Ubuntu Server:

- встановлення Python 3.12+;
- встановлення PostgreSQL;
- створення бази `telegram_inbox`;
- створення користувача PostgreSQL `telegram_inbox_user`;
- клонування проєкту;
- створення Linux-користувача `telegraminbox`;
- створення venv;
- встановлення `requirements.txt`;
- налаштування `.env`;
- запуск Alembic migrations;
- створення першого адміна через CLI;
- перевірка локального запуску;
- створення systemd service для бота;
- створення systemd service для web;
- налаштування Nginx reverse proxy;
- налаштування HTTPS через Certbot;
- налаштування firewall;
- перевірка логів;
- перезапуск сервісів;
- оновлення проєкту після `git pull`.

### Backup / restore

Додати приклади:

```bash
pg_dump -U telegram_inbox_user -h localhost telegram_inbox > telegram_inbox_backup.sql
psql -U telegram_inbox_user -h localhost telegram_inbox < telegram_inbox_backup.sql
```

Пояснити:

- backup-файли не зберігати в публічній папці сайту;
- backup-файли не комітити в Git;
- бажано зберігати backup у захищеній директорії або зовнішньому сховищі.

### Логи

Додати команди:

```bash
journalctl -u telegram-inbox-bot -f
journalctl -u telegram-inbox-web -f
systemctl status telegram-inbox-bot
systemctl status telegram-inbox-web
systemctl restart telegram-inbox-bot
systemctl restart telegram-inbox-web
```

### Критерії готовності

- README пояснює локальний запуск і базове використання.
- DEPLOY дозволяє розгорнути застосунок на чистому Ubuntu Server.
- Документація не містить реальних секретів.

## 17. Фаза 15: Тестування і security review

### Functional tests

- `/start` створює або оновлює користувача.
- Incoming text message зберігається в базу.
- Admin notification надсилається.
- Reply з адмінки доставляється користувачу.
- Failed Telegram delivery зберігає outgoing message зі статусом `failed`.
- Blocked user не може надсилати повідомлення.
- Rate limit працює.
- Search/filter у messages працює.
- Search/filter у users працює.
- Mark as read працює.
- Logout працює.

### Security checks

- Без login не відкриваються:
  - `/`;
  - `/messages`;
  - `/messages/{id}`;
  - `/users`;
  - `/users/{id}`.
- POST routes без CSRF не виконуються.
- POST routes без сесії не виконуються.
- Після 5 неправильних login attempts IP тимчасово блокується.
- 2FA code має expiration.
- 2FA code не зберігається відкритим текстом.
- Session cookie має `Secure`, `HttpOnly`, `SameSite`.
- `.env` у `.gitignore`.
- `/docs` і `/redoc` вимкнені у production.
- Nginx блокує hidden files.
- PostgreSQL не слухає публічний інтерфейс.
- FastAPI не слухає `0.0.0.0` у production.
- Логи не містять паролів, токенів або cookies.

### Deployment checks

- DNS A-запис `admintextbot.hotzagor.tech -> IP VPS` створений.
- Certbot видав сертифікат для `admintextbot.hotzagor.tech`.
- `systemctl status telegram-inbox-web` показує active.
- `systemctl status telegram-inbox-bot` показує active.
- `curl http://127.0.0.1:8000/health` працює на сервері.
- Зовні порт `8000` недоступний.
- Зовні працює тільки HTTPS-адмінка.

### Критерії готовності

- Основні happy paths працюють.
- Основні security checks пройдені.
- Відомі ризики задокументовані.
- Застосунок можна деплоїти на production VPS.

## 18. Рекомендований порядок реалізації

1. Ініціалізація проєкту, конфіг, логування.
2. Database layer, моделі, Alembic.
3. Security helpers, sessions, password hashing, CSRF.
4. CLI для створення першого адміна.
5. Telegram bot MVP.
6. Rate limit і admin notifications.
7. Web auth, brute-force protection, optional 2FA.
8. Dashboard.
9. Messages section.
10. Users section і reply flow.
11. UX polish.
12. Service endpoints і production behavior.
13. Nginx, systemd, Docker Compose.
14. README і DEPLOY.
15. End-to-end testing і security review.

## 19. Definition of Done

Проєкт вважається готовим, коли:

- Telegram-бот приймає повідомлення користувачів.
- Усі повідомлення зберігаються в PostgreSQL.
- Адмін отримує Telegram-сповіщення про нові повідомлення.
- Веб-адмінка доступна на `https://admintextbot.hotzagor.tech`.
- Без авторизації адмінка недоступна.
- Єдиний адмін може переглядати dashboard, users, messages і user detail.
- Адмін може відповідати користувачам через бота.
- Помилки Telegram API коректно показуються в адмінці і записуються в базу.
- Заблоковані користувачі не можуть надсилати повідомлення.
- Rate limit захищає від спаму.
- Brute-force protection захищає login.
- Optional Telegram 2FA працює.
- Production конфіги Nginx і systemd додані.
- `README.md` і `DEPLOY.md` достатні для запуску і деплою.
- `.env.example` містить тільки placeholders.
- Реальні секрети не потрапляють у репозиторій.
- `/docs` і `/redoc` не відкриті в production.
- Порт `8000` не відкритий назовні.
- Firewall відкриває тільки `22`, `80`, `443`.
- Є documented backup/restore flow.

## 20. Ризики і рішення

| Ризик | Рішення |
| --- | --- |
| Витік Telegram token або SECRET_KEY | `.env` у `.gitignore`, `.env.example` тільки з `CHANGE_ME`, не логувати env values |
| Несанкціонований доступ до адмінки | Nginx Basic Auth, app login, optional 2FA, brute-force protection, secure cookies |
| Публічний доступ до FastAPI напряму | FastAPI слухає тільки `127.0.0.1:8000`, firewall не відкриває `8000` |
| PostgreSQL доступний з інтернету | PostgreSQL bind тільки localhost, firewall не відкриває порт БД |
| Спам у бот | per-user rate limit, логування перевищень |
| Telegram API помилки при відповіді | outgoing message зі статусом `failed`, `error_text`, зрозуміла помилка в UI |
| Непідтримувані вкладення ламають бота | fallback handler для unsupported message types |
| Втрата даних | documented `pg_dump` backup і restore |
| Stack trace у production | debug off, custom error pages, centralized logging |
| Відкриті `/docs` і `/redoc` | вимкнути у production або закрити авторизацією |

## 21. Після MVP

Ці задачі не блокують першу production-версію, але можуть бути корисними після запуску:

- Full-text search по повідомленнях у PostgreSQL.
- Export переписки в CSV або JSON.
- Admin audit log для дій block/unblock/reply/login.
- Server-side sessions замість signed cookies, якщо потрібен примусовий logout.
- IP allowlist для адмінки.
- Підтримка metadata для фото, документів і відео.
- Background job для cleanup expired 2FA codes.
- Healthcheck для database connectivity.
- Automated tests через `pytest`.
- CI workflow для lint/test.
