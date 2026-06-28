Створи production-ready проєкт Telegram Inbox Bot з веб-адмінкою на окремому піддомені.

ВАЖЛИВО:
Проєкт має бути не демо, не заглушка, а повністю робочий застосунок, який можна задеплоїти на Ubuntu Server/VPS.

Мій реальний домен для адмінки:
https://admintextbot.hotzagor.tech

Мета проєкту:
Мені потрібен Telegram-бот, через якого люди можуть писати мені повідомлення, не знаючи мого особистого Telegram-акаунта. Усі повідомлення мають зберігатися в базі даних. Я як єдиний адмін повинен заходити на повністю закриту веб-адмінку за адресою:

https://admintextbot.hotzagor.tech

В адмінці я маю бачити користувачів, повідомлення, історію переписки та мати можливість відповідати користувачам через Telegram-бота.

Головна вимога:
Ніхто, крім мене, не повинен мати доступу до адмінки та повідомлень.

Якщо стороння людина відкриє:
https://admintextbot.hotzagor.tech

вона має побачити тільки сторінку логіну, Basic Auth або отримати 403 Forbidden. Без авторизації жодна сторінка адмінки не повинна відкриватися.

Основний стек:

* Python 3.12+
* aiogram 3 для Telegram-бота
* FastAPI для веб-адмінки
* SQLAlchemy 2.x
* Alembic для міграцій
* PostgreSQL для production
* SQLite дозволити тільки для локального dev-режиму
* Jinja2 templates для HTML-адмінки
* Bootstrap 5 або чистий сучасний CSS
* Uvicorn або Gunicorn + UvicornWorker для запуску FastAPI
* Nginx як reverse proxy
* Let’s Encrypt / Certbot для HTTPS
* systemd services для автозапуску
* python-dotenv або pydantic-settings для .env
* passlib/bcrypt або argon2 для хешування паролів

Архітектура:

1. Telegram-бот працює окремим systemd-сервісом.
2. Web admin працює окремим systemd-сервісом.
3. FastAPI слухає тільки localhost:
   127.0.0.1:8000
4. Назовні відкритий тільки Nginx через HTTPS.
5. PostgreSQL працює локально на сервері і не відкритий в інтернет.
6. Усі секрети зберігаються тільки в .env.
7. Код не повинен містити токенів, паролів або приватних ключів.
8. Порт 8000 не відкривати назовні.
9. Відкритими назовні мають бути тільки:

   * 22 для SSH;
   * 80 для HTTP/Certbot;
   * 443 для HTTPS.

Домен:

* Адмінка: https://admintextbot.hotzagor.tech
* ADMIN_PANEL_BASE_URL=https://admintextbot.hotzagor.tech
* Nginx server_name admintextbot.hotzagor.tech;
* SSL-сертифікат має бути випущений саме для admintextbot.hotzagor.tech.

Структура проєкту:

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

Функціонал Telegram-бота:

1. Команда /start:

   * Привітати користувача.
   * Пояснити, що він може написати повідомлення власнику сайту.
   * Пояснити, що відповідь прийде через цього бота.
   * Зберегти або оновити користувача в базі.
   * Зберегти:

     * telegram_id;
     * username;
     * first_name;
     * last_name;
     * language_code;
     * created_at;
     * updated_at;
     * last_message_at.

2. Прийом повідомлень:

   * Бот має приймати текстові повідомлення від користувачів.
   * Кожне повідомлення треба зберігати в PostgreSQL.
   * Повідомлення користувача має мати:

     * direction = incoming;
     * status = new.
   * Якщо користувач заблокований, бот не повинен приймати повідомлення.
   * Заблокованому користувачу показати коротке повідомлення, що надсилання повідомлень недоступне.

3. Сповіщення адміну:

   * Коли приходить нове повідомлення, бот має надіслати мені як адміну сповіщення в Telegram.
   * ADMIN_TELEGRAM_ID береться з .env.
   * У сповіщенні показати:

     * ім’я користувача;
     * username, якщо є;
     * telegram_id;
     * текст повідомлення;
     * дату і час;
     * посилання на сторінку цього користувача в адмінці на https://admintextbot.hotzagor.tech.

4. Відповіді користувачам:

   * Адмін має відповідати користувачу з веб-адмінки.
   * Відповідь має відправлятися користувачу через Telegram Bot API.
   * Відповідь має зберігатися в базі як outgoing message.
   * Якщо користувач заблокував бота або Telegram повернув помилку, це треба коректно показати в адмінці.
   * У разі помилки створити outgoing message зі статусом failed і записати error_text.

5. Захист від спаму:

   * Додати rate limit: не більше 5 повідомлень за хвилину від одного користувача.
   * RATE_LIMIT_MESSAGES_PER_MINUTE має братися з .env.
   * Якщо ліміт перевищено, бот має попросити користувача зачекати.
   * Такі події треба логувати.

6. Підтримка вкладень:

   * На першому етапі обов’язково підтримати текстові повідомлення.
   * Якщо користувач надсилає фото, документ, відео або інший файл, зробити один із варіантів:

     * або зберігати metadata вкладення;
     * або акуратно відповідати: “Файли поки не підтримуються, напишіть, будь ласка, текстом.”
   * Не допускати падіння бота через непідтримуваний тип повідомлення.

Функціонал веб-адмінки:

1. Приватна авторизація:

   * Адмінка має бути повністю закрита.
   * Без логіну не можна відкрити жодну сторінку адмінки.
   * Публічної реєстрації бути не повинно.
   * За замовчуванням має бути тільки один адмін.
   * Перший адмін створюється тільки через CLI-команду на сервері.
   * Пароль адміна не можна зберігати відкритим текстом.
   * Пароль має зберігатися тільки у вигляді hash.
   * Додати logout.
   * Сесії зробити безпечними через signed cookie або server-side session.
   * SECRET_KEY брати тільки з .env.

2. Додатковий захист доступу:
   Реалізувати або підготувати конфіг для кількох рівнів захисту:

   Рівень 1:

   * Nginx Basic Auth перед входом в адмінку.

   Рівень 2:

   * Логін і пароль у самій FastAPI-адмінці.

   Рівень 3:

   * Опціональна Telegram 2FA.
   * Після введення логіна і пароля бот надсилає одноразовий код на ADMIN_TELEGRAM_ID.
   * Вхід дозволяється тільки після введення правильного коду.
   * Код має мати обмежений термін дії, наприклад 5 хвилин.
   * Код не зберігати відкритим текстом, тільки hash.

   Рівень 4:

   * Захист від brute-force.
   * Після 5 неправильних спроб входу тимчасово блокувати логін з цього IP.

   Рівень 5:

   * Secure, HttpOnly, SameSite cookies.

   Рівень 6:

   * X-Robots-Tag: noindex, nofollow.

   Рівень 7:

   * У production вимкнути відкриті /docs і /redoc.

3. Dashboard:
   На головній сторінці адмінки показати:

   * загальну кількість користувачів;
   * загальну кількість повідомлень;
   * кількість нових повідомлень;
   * кількість заблокованих користувачів;
   * останні 10 повідомлень;
   * швидке посилання на непрочитані повідомлення.

4. Сторінка повідомлень:

   * Таблиця всіх повідомлень.
   * Поля:

     * ID;
     * дата;
     * користувач;
     * username;
     * telegram_id;
     * текст;
     * direction;
     * status;
     * кнопка “Відкрити”.
   * Пошук по:

     * тексту;
     * username;
     * telegram_id;
     * імені.
   * Фільтри:

     * new;
     * read;
     * answered;
     * failed;
     * incoming;
     * outgoing;
     * за датою.

5. Сторінка користувачів:

   * Таблиця всіх користувачів.
   * Пошук.
   * Фільтр заблокованих.
   * Показати:

     * ім’я;
     * username;
     * telegram_id;
     * кількість повідомлень;
     * дата останнього повідомлення;
     * статус blocked/not blocked.
   * Додати перехід на сторінку конкретного користувача.

6. Сторінка конкретного користувача:

   * Показати дані користувача:

     * telegram_id;
     * username;
     * first_name;
     * last_name;
     * language_code;
     * created_at;
     * updated_at;
     * last_message_at;
     * is_blocked.
   * Показати історію переписки у вигляді чату.
   * Непрочитані повідомлення виділяти.
   * Додати форму відповіді користувачу.
   * Після відповіді:

     * відправити повідомлення користувачу через Telegram-бота;
     * зберегти відповідь у базі як outgoing;
     * змінити статус вхідних повідомлень на answered або read.
   * Додати кнопки:

     * “Позначити як прочитане”;
     * “Заблокувати”;
     * “Розблокувати”.

7. UX адмінки:

   * Зробити простий, чистий, сучасний дизайн.
   * Інтерфейс має бути зручний на ПК.
   * Інтерфейс має нормально відкриватися з телефона.
   * Непрочитані повідомлення виділяти візуально.
   * Довгі повідомлення обрізати в таблиці, але повністю показувати на сторінці переписки.
   * Додати зрозумілі повідомлення про успіх і помилки.

Моделі бази даних:

User:

* id
* telegram_id, unique, indexed
* username, nullable, indexed
* first_name, nullable
* last_name, nullable
* language_code, nullable
* is_blocked, default false
* created_at
* updated_at
* last_message_at

Message:

* id
* user_id, foreign key
* direction: incoming/outgoing
* text
* status: new/read/answered/failed
* telegram_message_id, nullable
* error_text, nullable
* created_at

AdminUser:

* id
* username, unique
* password_hash
* is_active
* created_at
* updated_at
* last_login_at

LoginAttempt:

* id
* ip_address
* username
* success
* created_at

TwoFactorCode:

* id
* admin_user_id
* code_hash
* expires_at
* used_at
* created_at

Settings:

* id
* key
* value

Можна додати додаткові поля, якщо це потрібно для якісної реалізації.

Routes / endpoints:

Auth:

* GET /login
* POST /login
* GET /2fa
* POST /2fa
* POST /logout

Admin:

* GET /
* GET /messages
* GET /messages/{id}
* POST /messages/{id}/read
* GET /users
* GET /users/{id}
* POST /users/{id}/reply
* POST /users/{id}/block
* POST /users/{id}/unblock

Service:

* GET /health
* GET /version

Важливо для production:

* Не робити публічну API-документацію для адмінки.
* /docs і /redoc у production мають бути вимкнені або доступні тільки після авторизації.
* Не показувати stack trace в браузері.
* Усі помилки логувати.
* У production debug має бути вимкнений.
* Не логувати паролі, токени, session cookies.
* .env має бути в .gitignore.
* TELEGRAM_BOT_TOKEN не має потрапляти в Git.
* SECRET_KEY не має потрапляти в Git.

.env.example має містити:

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

Deployment requirements:

1. Написати DEPLOY.md з повною інструкцією для Ubuntu Server:

   * встановлення Python 3.12+;
   * встановлення PostgreSQL;
   * створення бази даних telegram_inbox;
   * створення користувача PostgreSQL telegram_inbox_user;
   * клонування проєкту;
   * створення окремого Linux-користувача, наприклад telegraminbox;
   * створення venv;
   * встановлення requirements.txt;
   * налаштування .env;
   * запуск Alembic migrations;
   * створення першого адміна через CLI;
   * перевірка локального запуску;
   * створення systemd-сервісу для бота;
   * створення systemd-сервісу для web;
   * налаштування Nginx reverse proxy;
   * налаштування HTTPS через Certbot;
   * налаштування firewall;
   * перевірка логів;
   * перезапуск сервісів;
   * оновлення проєкту після git pull.

2. systemd service для вебу:

   * запускати FastAPI через uvicorn або gunicorn;
   * працювати від окремого Linux-користувача telegraminbox;
   * автозапуск після reboot;
   * restart on failure;
   * environment file брати з .env.

3. systemd service для бота:

   * запускати app.bot.main;
   * працювати від окремого Linux-користувача telegraminbox;
   * автозапуск після reboot;
   * restart on failure;
   * environment file брати з .env.

4. Nginx production-конфіг:

   * server_name admintextbot.hotzagor.tech;
   * proxy_pass на 127.0.0.1:8000;
   * HTTPS;
   * secure headers;
   * client_max_body_size;
   * rate limit для login;
   * опціональний Basic Auth;
   * опціональний allow/deny по IP;
   * X-Robots-Tag noindex, nofollow;
   * заборонити доступ до прихованих файлів типу .env, .git.

5. Firewall:

   * відкрити тільки 22, 80, 443;
   * PostgreSQL не відкривати назовні;
   * FastAPI порт 8000 не відкривати назовні;
   * 8000 має слухати тільки 127.0.0.1.

6. Безпечні заголовки Nginx:

   * X-Frame-Options DENY;
   * X-Content-Type-Options nosniff;
   * Referrer-Policy no-referrer-when-downgrade;
   * X-Robots-Tag noindex, nofollow;
   * Content-Security-Policy, якщо можливо;
   * Permissions-Policy, якщо можливо.

7. SSL:

   * Додати інструкцію для Certbot.
   * Сертифікат має бути для:
     admintextbot.hotzagor.tech
   * Після встановлення HTTPS перевірити автоматичне оновлення сертифіката.

8. DNS:
   У DEPLOY.md додати, що перед деплоєм потрібно створити DNS A-запис:

   admintextbot.hotzagor.tech -> IP VPS/сервера

README.md має містити:

* опис проєкту;
* як створити Telegram-бота через BotFather;
* як отримати TELEGRAM_BOT_TOKEN;
* як дізнатися свій ADMIN_TELEGRAM_ID;
* як підготувати сервер;
* як налаштувати DNS A-запис для admintextbot.hotzagor.tech;
* як налаштувати .env;
* як встановити залежності;
* як створити базу PostgreSQL;
* як запустити міграції;
* як створити першого адміна;
* як запустити бота;
* як запустити веб-адмінку;
* як увійти в адмінку;
* як відповідати користувачам;
* як блокувати користувачів;
* як дивитися логи;
* як перезапускати сервіси;
* як оновлювати проєкт;
* як робити backup бази даних.

CLI-команда для створення першого адміна:

python -m app.cli.create_admin

Вона має:

* запитати username;
* запитати password;
* попросити повторити password;
* захешувати пароль;
* створити першого адміна;
* якщо адмін вже існує, не створювати другого без явного прапорця;
* не виводити пароль у консоль.

Безпека:

* Ніякої публічної реєстрації.
* Тільки один адмін за замовчуванням.
* Пароль не зберігати відкрито.
* Секрети тільки в .env.
* .env має бути в .gitignore.
* Додати .gitignore.
* Додати CSRF-захист для POST-форм або реалізувати безпечний механізм перевірки POST-запитів.
* POST-запити мають перевіряти авторизацію.
* Додати захист від brute-force на login.
* Додати Telegram 2FA як опцію.
* Не логувати паролі, токени, session cookies.
* У production вимкнути debug.
* У production вимкнути відкриті /docs і /redoc.
* Додати graceful error pages 403, 404, 500.
* Додати логування помилок.
* Додати перевірку прав доступу для кожної admin route.
* Додати перевірку, що неавторизований користувач не може напряму відкрити /users, /messages або інші сторінки.

Бекапи:

* Додати в README або DEPLOY.md приклад команди для backup PostgreSQL:
  pg_dump
* Додати приклад команди для restore.
* Пояснити, де зберігати backup-файли.
* Не зберігати backup у публічній папці сайту.

Логи:

* Логи бота і вебу мають бути доступні через journalctl.
* У DEPLOY.md додати приклади:

  * journalctl -u telegram-inbox-bot -f
  * journalctl -u telegram-inbox-web -f
  * systemctl status telegram-inbox-bot
  * systemctl status telegram-inbox-web
  * systemctl restart telegram-inbox-bot
  * systemctl restart telegram-inbox-web

Очікуваний результат:
Після деплою на Ubuntu Server я відкриваю:

https://admintextbot.hotzagor.tech

Бачу закриту сторінку входу або Basic Auth. Після входу як єдиний адмін бачу dashboard, список повідомлень, список користувачів, історію переписки і можу відповідати користувачам через Telegram-бота.

Користувачі пишуть у Telegram-бота. Бот зберігає повідомлення в PostgreSQL. Я отримую Telegram-сповіщення. Потім я заходжу на:

https://admintextbot.hotzagor.tech

читаю повідомлення і відповідаю через бота. Користувач отримує відповідь у Telegram від імені бота.

Додаткові вимоги до якості:

* Код має бути чистий і зрозумілий.
* Не робити все в одному файлі.
* Дотримуватися нормальної структури проєкту.
* Додати коментарі там, де логіка складна.
* Додати зрозумілі назви функцій.
* Додати базову валідацію форм.
* Додати нормальну обробку помилок.
* Додати міграції Alembic.
* Додати .env.example.
* Додати README.md.
* Додати DEPLOY.md.
* Додати systemd service files.
* Додати Nginx config для admintextbot.hotzagor.tech.
* Додати docker-compose.yml для локального запуску PostgreSQL, якщо це доречно.
* Додати можливість легко перейти з SQLite dev-режиму на PostgreSQL production через DATABASE_URL.

Не використовуй реальні токени або паролі. Усі секрети залиш як CHANGE_ME.
