# Сервис выдачи книг в библиотеке (`anna_akulova`)

Учебный сервис курсовой работы по дисциплине «Оптимизация клиент-серверных приложений».  
Вариант 1: выдаёт экземпляр читателю (если экземпляр свободен и нет просроченных выдач), принимает возврат, считает просрочку и штраф, показывает сводку.

## Требования

- Python 3.11+ (проверено на 3.14);
- PostgreSQL 16;
- Docker / Docker Compose (для базы данных).

## Установка и запуск

```bash
git clone <адрес репозитория>
cd HW1_oksp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
docker compose up -d
python -c "from app.db import init_schema; init_schema()"
python scripts/seed.py --volume small
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Рабочее наполнение (вместо `small`):

```bash
python scripts/seed.py --volume work
```

## Переменные окружения

| Переменная     | Назначение                         | Пример                                                         |
|----------------|------------------------------------|----------------------------------------------------------------|
| DATABASE_URL   | подключение к PostgreSQL           | postgresql+psycopg://anna_akulova:changeme@localhost:5432/anna_akulova |
| APP_PORT       | порт сервиса                       | 8080                                                           |
| SECRET_KEY     | секрет для хеша паролей            | changeme-secret-key                                            |
| SCHEMA_NAME    | схема БД (личный маркер)           | anna_akulova                                                   |
| FINE_PER_DAY   | штраф за день просрочки, ₽         | 10                                                             |
| LOAN_DAYS      | срок выдачи, дни                   | 14                                                             |

## Проверка работоспособности

Интерфейс: http://localhost:8080  
Учётная запись: `demo` / `demo`  

Экраны:

1. список выдач с фильтром и постраничным выводом — `/`
2. карточка выдачи со связанными сущностями — `/loans/{id}`
3. сводка — `/summary`

## Тесты

```bash
pytest -q
```

## Программный интерфейс

| Метод и путь                 | Параметры                                      | Ответ                                      | Ошибки        |
|------------------------------|------------------------------------------------|--------------------------------------------|---------------|
| POST /api/auth/login         | username, password                             | `{"access_token": "...", "token_type": "bearer"}` | 401      |
| GET /api/loans               | page, size, status (`open\|returned\|overdue`), q, reader_id | `{"items": [...], "total": N, "page", "size"}` | 401, 422 |
| GET /api/loans/{id}          | —                                              | объект выдачи со связанными сущностями     | 401, 404      |
| POST /api/loans              | reader_id, copy_id, issued_at?                 | 201 и созданная выдача                     | 401, 404, 409 |
| POST /api/loans/{id}/return  | returned_at?                                    | выдача с overdue_days и fine_amount        | 401, 404, 409 |
| GET /api/summary             | —                                              | copies_on_hand, overdue_on_hand, popular_books, total_loans, total_fines | 401 |
| GET /api/health              | —                                              | `{"status":"ok","project":"anna_akulova"}` | —             |

Авторизация API: заголовок `Authorization: Bearer <token>`.

## Замеры

При запущенном сервисе:

```bash
python scripts/measure.py --volume-label small --repeats 20 --warmup 3
python scripts/measure.py --volume-label work --repeats 20 --warmup 3
```

## Объёмы наполнения

| Сущность   | small | work   |
|------------|-------|--------|
| читатели   | 50    | 3 000  |
| книги      | 100   | 10 000 |
| экземпляры | 200   | 30 000 |
| выдачи     | 300   | 80 000 |
