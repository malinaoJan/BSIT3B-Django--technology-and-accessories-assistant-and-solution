# TECHFIX — SQL folder

Database + ERD for the `projectv3` system.

Both SQL files mirror the current Django schema: 10 framework tables
(`auth_*`, `django_*`) + 6 app tables (`techfix_*`, `tblinfo`).

## Quick start
- **MySQL:** import `techfix_database.sql` (creates `techfix_db`), then run
  `python manage.py migrate --fake` once so Django records the migrations.
- **SQLite:** `sqlite3 db.sqlite3 < techfix_database_sqlite.sql`, then
  `python manage.py migrate --fake`. (Or, on an empty database, just run
  `python manage.py migrate`.)
- **ERD image:** `ERD.png` (Word/PPT) / `ERD.svg` (browser/vector).
- **ERD source:** `ERD.mmd` (Mermaid) / `ERD.puml` (PlantUML).
- **Docs:** `ERD.md` — data dictionary + relationships + usage.

See `ERD.md` for the full data dictionary.
