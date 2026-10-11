import os

# Не трогаем PostgreSQL при прогоне модульных тестов.
os.environ["SKIP_DB_INIT"] = "1"
