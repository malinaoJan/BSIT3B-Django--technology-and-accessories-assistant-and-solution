# TECHFIX — SQL folder

Database scripts + ERD for the `projectv3` system.

Current schema (Django 6.1.2): **26 tables** — 17 framework tables
(`auth_*`, `django_*`, `account_*`, `socialaccount_*`) + 9 application tables
(`techfix_*`, `users_phoneprofile`, `tblinfo`).

## Files

| File | Engine | Contents |
|---|---|---|
| `techfix_database.sql` | MySQL / MariaDB | Schema only (26 tables with PK/FK/indexes/checks). Creates and selects `techfix_db`. |
| `techfix_database_dump.sql` | MySQL / MariaDB | Full dump of the live `techfix_db`: schema + all rows + `django_migrations`. Generated 2026-11-11. |
| `techfix_database_sqlite.sql` | SQLite | Schema only — exactly what `python manage.py migrate` creates. |
| `techfix_database_dump_sqlite.sql` | SQLite | Data dump of the legacy `projectv3/db.sqlite3` (2026-11-10), kept as a backup. |
| `ERD.mmd` / `ERD.puml` | — | Editable ERD sources (Mermaid / PlantUML). |
| `ERD.svg` / `ERD.png` | — | Rendered diagrams (regenerated 2026-11-11 from `ERD.puml`). |
| `ERD.md` | — | Data dictionary + relationships + usage. |

## Quick start

**MySQL — full restore (schema + data):**

```bash
mysql -u root -e "CREATE DATABASE IF NOT EXISTS techfix_db CHARACTER SET utf8mb4"
mysql -u root techfix_db < techfix_database_dump.sql
```

The dump includes `django_migrations`, so no extra `migrate --fake` step is needed.

**MySQL — empty schema:**

```bash
mysql -u root < techfix_database.sql
python manage.py migrate --fake
```

**SQLite — empty schema:**

```bash
sqlite3 db.sqlite3 < techfix_database_sqlite.sql
python manage.py migrate --fake
```

Or, on an empty database, just run `python manage.py migrate`.

See `ERD.md` for the full data dictionary.
