# TECHFIX System — Database & ERD

**Project:** `projectv3` (Django `apps.core` + `apps.info` + `apps.users`/auth)
**Source of truth:** `apps/core/models.py`, `apps/info/models.py`, `apps/scoping.py`, live `db.sqlite3`
**Generated:** 2026-10-28

## Files in this folder

| File | Purpose |
|---|---|
| `techfix_database.sql` | Full database for **MySQL / MariaDB** (`CREATE DATABASE techfix_db` + 16 tables: 10 Django framework + 6 app tables, with PK/FK/indexes/checks). Import with phpMyAdmin or `mysql < techfix_database.sql`. |
| `techfix_database_sqlite.sql` | Same schema for **SQLite** (what the project runs on by default). Apply with `sqlite3 db.sqlite3 < techfix_database_sqlite.sql`. |
| `ERD.mmd` | Editable ERD source (Mermaid `erDiagram`). Paste into https://mermaid.live or any Mermaid viewer. |
| `ERD.puml` | Editable ERD source (PlantUML). Open with a PlantUML plugin or http://www.plantuml.com/plantuml/uml. |
| `ERD.svg` | Vector diagram (opens in any browser, scales for reports). |
| `ERD.png` | Raster diagram (for Word / PPT / PDF submissions). |
| `ERD.md` | This file — data dictionary + relationships. |

## ERD (preview)

![TECHFIX ERD](ERD.png)

> If the image does not preview in your editor, open `ERD.png` or `ERD.svg` directly.
> The editable definitions are `ERD.mmd` (Mermaid) and `ERD.puml` (PlantUML).

```mermaid
erDiagram
    AUTH_USER ||--o{ TBLINFO : "owns (1:N)"
    TECHFIX_CATEGORY ||--o{ TECHFIX_PRODUCT : "groups (1:N)"
    TECHFIX_CATEGORY ||--o{ TECHFIX_ACCESSORY : "groups (1:N)"
    TECHFIX_CATEGORY ||--o{ TECHFIX_SOLUTION : "groups (1:N)"
    TECHFIX_PRODUCT ||--o{ TECHFIX_SOLUTION : "explains (1:N)"
    TECHFIX_PRODUCT ||--o{ TECHFIX_ACCESSORY_COMPATIBLE_PRODUCTS : "matched in (1:N)"
    TECHFIX_ACCESSORY ||--o{ TECHFIX_ACCESSORY_COMPATIBLE_PRODUCTS : "matched in (1:N)"
```

## Entities (data dictionary)

### 1. `auth_user` — Django default user (used by `apps.users`)
| Column | Type | Key | Notes |
|---|---|---|---|
| id | INT AI | PK | |
| username | VARCHAR(150) | UNIQUE | login name |
| password | VARCHAR(128) | | hashed |
| first_name / last_name | VARCHAR(150) | | |
| email | VARCHAR(254) | | |
| is_superuser / is_staff / is_active | TINYINT(1) | | superuser sees all `tblinfo`; others see own only (`apps/scoping.py`) |
| last_login | DATETIME NULL | | |
| date_joined | DATETIME | | |

### 2. `techfix_category` — grouping (ex. Laptops, Audio, Chargers)
| Column | Type | Key | Notes |
|---|---|---|---|
| id | BIGINT AI | PK | table `techfix_category` |
| name | VARCHAR(100) | UNIQUE | |
| description | TEXT | | |
| created_at | DATETIME | | auto_now_add |

### 3. `techfix_product` — main tech devices (laptop, phone, printer, router)
| Column | Type | Key | Notes |
|---|---|---|---|
| id | BIGINT AI | PK | table `techfix_product` |
| name | VARCHAR(255) | | |
| category_id | BIGINT NULL | FK → category.id | `SET NULL`, `related_name='products'` |
| brand | VARCHAR(100) | | |
| description | TEXT | | |
| specifications | TEXT | | RAM, CPU, Storage, etc. |
| price | DECIMAL(10,2) | | Django default 0 |
| stock_quantity | INT UNSIGNED | | Django default 0; DB CHECK >= 0 |
| image | VARCHAR(100) NULL | | `upload_to='products/'` |
| created_at / updated_at | DATETIME | | |

### 4. `techfix_accessory` — add-ons (cases, chargers, keyboards, earbuds, cables)
| Column | Type | Key | Notes |
|---|---|---|---|
| id | BIGINT AI | PK | table `techfix_accessory` |
| name | VARCHAR(255) | | |
| category_id | BIGINT NULL | FK → category.id | `SET NULL`, `related_name='accessories'` |
| brand | VARCHAR(100) | | |
| description | TEXT | | |
| price | DECIMAL(10,2) | | Django default 0 |
| compatibility_notes | TEXT | | ex. Compatible with USB-C laptops |
| stock_quantity | INT UNSIGNED | | Django default 0; DB CHECK >= 0 |
| image | VARCHAR(100) NULL | | `upload_to='accessories/'` |
| created_at | DATETIME | | |

### 5. `techfix_accessory_compatible_products` — M:N junction (auto-created by Django)
`Accessory.compatible_products = ManyToManyField(Product, related_name='compatible_accessories')`
| Column | Type | Key | Notes |
|---|---|---|---|
| id | BIGINT AI | PK | |
| accessory_id | BIGINT | FK → accessory.id, `CASCADE` | part of `UNIQUE(accessory_id, product_id)` |
| product_id | BIGINT | FK → product.id, `CASCADE` | part of `UNIQUE(accessory_id, product_id)` |

### 6. `techfix_solution` — step-by-step fix for a common tech problem
| Column | Type | Key | Notes |
|---|---|---|---|
| id | BIGINT AI | PK | table `techfix_solution` |
| title | VARCHAR(255) | | |
| problem_description | TEXT | | symptoms / common issue |
| steps | TEXT | | Step 1, Step 2, … |
| difficulty_level | VARCHAR(10) | | `Easy` / `Medium` / `Hard` (Django choices) |
| category_id | BIGINT NULL | FK → category.id | `SET NULL` |
| related_product_id | BIGINT NULL | FK → product.id | `SET NULL`, `related_name='solutions'` |
| video_url | VARCHAR(200) | | blank allowed |
| created_at / updated_at | DATETIME | | |

### 7. `tblinfo` — `apps.info.Info` (name/age/address/email, privately owned)
| Column | Type | Key | Notes |
|---|---|---|---|
| id | BIGINT AI | PK | `db_table='tblinfo'`, ordering by name |
| name | VARCHAR(255) | | |
| age | INT UNSIGNED | | Django validators 1–150; DB CHECK >= 0 |
| address | VARCHAR(255) | | |
| email | VARCHAR(255) | | blank allowed |
| user_id | INT NULL | FK → auth_user.id | `CASCADE`, `related_name='infos'` |
| created_at / updated_at | DATETIME | | |

## Supporting Django tables (not domain entities)

The ERD above shows the 7 domain/auth entities. The database also needs these
Django framework tables to run; both SQL scripts create them:

| Table | Purpose |
|---|---|
| `django_migrations` | Migration history used by `manage.py migrate` |
| `django_content_type` | Model/content-type registry |
| `auth_permission` | Permission definitions |
| `auth_group` | User groups |
| `auth_group_permissions` | M:N group → permission |
| `auth_user_groups` | M:N user → group |
| `auth_user_user_permissions` | M:N user → permission |
| `django_admin_log` | Django admin change history |
| `django_session` | Login sessions |

`auth_user` is shown in the ERD because `tblinfo.user_id` references it.

## Relationships (crow's foot: 1 ──∞)

| # | Parent (1) | Child (N) | FK | On delete | Meaning |
|---|---|---|---|---|---|
| R1 | `auth_user` | `tblinfo` | `tblinfo.user_id` | CASCADE | 1 user owns N info rows |
| R2 | `techfix_category` | `techfix_product` | `product.category_id` | SET NULL | 1 category groups N products |
| R3 | `techfix_category` | `techfix_accessory` | `accessory.category_id` | SET NULL | 1 category groups N accessories |
| R4 | `techfix_category` | `techfix_solution` | `solution.category_id` | SET NULL | 1 category groups N solutions |
| R5 | `techfix_product` | `techfix_solution` | `solution.related_product_id` | SET NULL | 1 product explained by N solutions |
| R6/R7 | `techfix_product` ↔ `techfix_accessory` | junction | `accessory_id`, `product_id` | CASCADE/CASCADE | M:N — accessory works with many products and vice versa |

## How to use

**MySQL / phpMyAdmin (database `techfix_db`):**
1. Open phpMyAdmin → Import → choose `techfix_database.sql` → Go.
2. Or CLI: `mysql -u root < SQL/techfix_database.sql`.
3. Then record the migrations once: `python manage.py migrate --fake`.
   (Update the MySQL `NAME` comment in `mysite/settings.py` if you switch the
   project from SQLite to MySQL.)

**SQLite (project default):**
`sqlite3 db.sqlite3 < SQL/techfix_database_sqlite.sql`
then `python manage.py migrate --fake` once to record the migrations.
For a normal install, just run `python manage.py migrate` on an empty database —
Django creates the identical tables.

**ERD for documentation:**
- Word/PPT/PDF → insert `ERD.png`.
- Report appendix / GitHub → embed `ERD.svg` or the Mermaid block above.
- Editing → modify `ERD.mmd` / `ERD.puml` and re-export.

## Notes / assumptions
- Only the **current** system is modeled (core + info + Django built-ins + auth_user). Stale tables still present in the old `db.sqlite3`/`bsitcrud.sql` dump (`catalog_*`, `tblcourse`, `tblstudents`, `tblattendance`, `tblquiz*`, etc.) are legacy and **not** part of this ERD, since they have no models in `projectv3/apps/`.
- `apps.users` has no custom model (`models.py` is empty), so the standard `auth_user` table is used.
- Cardinalities and `ON DELETE` rules are taken directly from the `on_delete=` arguments in `apps/core/models.py` and `apps/info/models.py`. Django enforces them in Python, so the SQL scripts create plain FKs (no SQL-level `ON DELETE` actions), matching the real Django schema.
- Both SQL files mirror the current live schema (`makemigrations --check` reports no changes) and include the Django framework tables required to run the project.
