
    # Migrations

    Schema is owned by Alembic in production (`create_all` in the app is a
    local-dev convenience only).

    ```bash
    # apply all migrations to the configured DATABASE_URL
    alembic upgrade head

    # after changing a model
    alembic revision --autogenerate -m "describe the change"
    alembic upgrade head
    ```
    