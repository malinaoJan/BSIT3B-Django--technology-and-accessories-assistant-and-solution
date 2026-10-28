-- ============================================================
-- TECHFIX System Database — SQLite version
-- Project: projectv3 (Django 6.1.2: apps.core + apps.info + Django built-ins)
-- Generated: 2026-10-28
--
-- Exact schema Django creates today via:
--   python manage.py migrate
-- (contenttypes.0001, auth.0001..0012, admin.0001..0003, sessions.0001,
--  core.0001_initial, info.0001_initial)
--
-- Domain tables:
--   techfix_category, techfix_product, techfix_accessory,
--   techfix_accessory_compatible_products, techfix_solution, tblinfo
--
-- Supporting Django tables:
--   django_migrations, django_content_type, auth_permission, auth_group,
--   auth_user, auth_group_permissions, auth_user_groups,
--   auth_user_user_permissions, django_admin_log, django_session
--
-- To apply to an empty database:
--   sqlite3 db.sqlite3 < techfix_database_sqlite.sql
-- Then record the migrations once:
--   python manage.py migrate --fake
-- (For a normal install, just run `python manage.py migrate` instead.)
-- ============================================================

PRAGMA foreign_keys = OFF;

-- ============================================================
-- Django framework tables
-- ============================================================

CREATE TABLE IF NOT EXISTS "django_migrations" (
  "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
  "app" varchar(255) NOT NULL,
  "name" varchar(255) NOT NULL,
  "applied" datetime NOT NULL
);

CREATE TABLE IF NOT EXISTS "django_content_type" (
  "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
  "app_label" varchar(100) NOT NULL,
  "model" varchar(100) NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS "django_content_type_app_label_model_76bd3d3b_uniq"
  ON "django_content_type" ("app_label", "model");

CREATE TABLE IF NOT EXISTS "auth_permission" (
  "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
  "content_type_id" integer NOT NULL REFERENCES "django_content_type" ("id") DEFERRABLE INITIALLY DEFERRED,
  "codename" varchar(100) NOT NULL,
  "name" varchar(255) NOT NULL
);
CREATE INDEX IF NOT EXISTS "auth_permission_content_type_id_2f476e4b"
  ON "auth_permission" ("content_type_id");
CREATE UNIQUE INDEX IF NOT EXISTS "auth_permission_content_type_id_codename_01ab375a_uniq"
  ON "auth_permission" ("content_type_id", "codename");

CREATE TABLE IF NOT EXISTS "auth_group" (
  "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
  "name" varchar(150) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS "auth_user" (
  "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
  "password" varchar(128) NOT NULL,
  "last_login" datetime NULL,
  "is_superuser" bool NOT NULL,
  "username" varchar(150) NOT NULL UNIQUE,
  "last_name" varchar(150) NOT NULL,
  "email" varchar(254) NOT NULL,
  "is_staff" bool NOT NULL,
  "is_active" bool NOT NULL,
  "date_joined" datetime NOT NULL,
  "first_name" varchar(150) NOT NULL
);

CREATE TABLE IF NOT EXISTS "auth_group_permissions" (
  "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
  "group_id" integer NOT NULL REFERENCES "auth_group" ("id") DEFERRABLE INITIALLY DEFERRED,
  "permission_id" integer NOT NULL REFERENCES "auth_permission" ("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS "auth_group_permissions_group_id_b120cbf9"
  ON "auth_group_permissions" ("group_id");
CREATE UNIQUE INDEX IF NOT EXISTS "auth_group_permissions_group_id_permission_id_0cd325b0_uniq"
  ON "auth_group_permissions" ("group_id", "permission_id");
CREATE INDEX IF NOT EXISTS "auth_group_permissions_permission_id_84c5c92e"
  ON "auth_group_permissions" ("permission_id");

CREATE TABLE IF NOT EXISTS "auth_user_groups" (
  "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
  "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED,
  "group_id" integer NOT NULL REFERENCES "auth_group" ("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS "auth_user_groups_group_id_97559544"
  ON "auth_user_groups" ("group_id");
CREATE INDEX IF NOT EXISTS "auth_user_groups_user_id_6a12ed8b"
  ON "auth_user_groups" ("user_id");
CREATE UNIQUE INDEX IF NOT EXISTS "auth_user_groups_user_id_group_id_94350c0c_uniq"
  ON "auth_user_groups" ("user_id", "group_id");

CREATE TABLE IF NOT EXISTS "auth_user_user_permissions" (
  "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
  "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED,
  "permission_id" integer NOT NULL REFERENCES "auth_permission" ("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS "auth_user_user_permissions_permission_id_1fbb5f2c"
  ON "auth_user_user_permissions" ("permission_id");
CREATE INDEX IF NOT EXISTS "auth_user_user_permissions_user_id_a95ead1b"
  ON "auth_user_user_permissions" ("user_id");
CREATE UNIQUE INDEX IF NOT EXISTS "auth_user_user_permissions_user_id_permission_id_14a6b632_uniq"
  ON "auth_user_user_permissions" ("user_id", "permission_id");

CREATE TABLE IF NOT EXISTS "django_admin_log" (
  "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
  "object_id" text NULL,
  "object_repr" varchar(200) NOT NULL,
  "action_flag" smallint unsigned NOT NULL CHECK ("action_flag" >= 0),
  "change_message" text NOT NULL,
  "content_type_id" integer NULL REFERENCES "django_content_type" ("id") DEFERRABLE INITIALLY DEFERRED,
  "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED,
  "action_time" datetime NOT NULL
);
CREATE INDEX IF NOT EXISTS "django_admin_log_content_type_id_c4bce8eb"
  ON "django_admin_log" ("content_type_id");
CREATE INDEX IF NOT EXISTS "django_admin_log_user_id_c564eba6"
  ON "django_admin_log" ("user_id");

CREATE TABLE IF NOT EXISTS "django_session" (
  "session_key" varchar(40) NOT NULL PRIMARY KEY,
  "session_data" text NOT NULL,
  "expire_date" datetime NOT NULL
);
CREATE INDEX IF NOT EXISTS "django_session_expire_date_a5c62663"
  ON "django_session" ("expire_date");

-- ============================================================
-- Application tables (apps.core / apps.info)
-- ============================================================

-- techfix_category
CREATE TABLE IF NOT EXISTS "techfix_category" (
  "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
  "name" varchar(100) NOT NULL UNIQUE,
  "description" text NOT NULL,
  "created_at" datetime NOT NULL
);

-- techfix_product
CREATE TABLE IF NOT EXISTS "techfix_product" (
  "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
  "name" varchar(255) NOT NULL,
  "brand" varchar(100) NOT NULL,
  "description" text NOT NULL,
  "specifications" text NOT NULL,
  "price" decimal NOT NULL,
  "stock_quantity" integer unsigned NOT NULL CHECK ("stock_quantity" >= 0),
  "image" varchar(100) NULL,
  "created_at" datetime NOT NULL,
  "updated_at" datetime NOT NULL,
  "category_id" bigint NULL REFERENCES "techfix_category" ("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS "techfix_product_category_id_d7b87187"
  ON "techfix_product" ("category_id");

-- techfix_accessory
CREATE TABLE IF NOT EXISTS "techfix_accessory" (
  "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
  "name" varchar(255) NOT NULL,
  "brand" varchar(100) NOT NULL,
  "description" text NOT NULL,
  "price" decimal NOT NULL,
  "compatibility_notes" text NOT NULL,
  "stock_quantity" integer unsigned NOT NULL CHECK ("stock_quantity" >= 0),
  "image" varchar(100) NULL,
  "created_at" datetime NOT NULL,
  "category_id" bigint NULL REFERENCES "techfix_category" ("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS "techfix_accessory_category_id_fe43e20e"
  ON "techfix_accessory" ("category_id");

-- techfix_accessory_compatible_products (M:N junction)
CREATE TABLE IF NOT EXISTS "techfix_accessory_compatible_products" (
  "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
  "accessory_id" bigint NOT NULL REFERENCES "techfix_accessory" ("id") DEFERRABLE INITIALLY DEFERRED,
  "product_id" bigint NOT NULL REFERENCES "techfix_product" ("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS "techfix_accessory_compatible_products_accessory_id_2bdcbf14"
  ON "techfix_accessory_compatible_products" ("accessory_id");
CREATE UNIQUE INDEX IF NOT EXISTS "techfix_accessory_compatible_products_accessory_id_product_id_f86249ad_uniq"
  ON "techfix_accessory_compatible_products" ("accessory_id", "product_id");
CREATE INDEX IF NOT EXISTS "techfix_accessory_compatible_products_product_id_10161dcf"
  ON "techfix_accessory_compatible_products" ("product_id");

-- techfix_solution
CREATE TABLE IF NOT EXISTS "techfix_solution" (
  "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
  "title" varchar(255) NOT NULL,
  "problem_description" text NOT NULL,
  "steps" text NOT NULL,
  "difficulty_level" varchar(10) NOT NULL,
  "video_url" varchar(200) NOT NULL,
  "created_at" datetime NOT NULL,
  "updated_at" datetime NOT NULL,
  "category_id" bigint NULL REFERENCES "techfix_category" ("id") DEFERRABLE INITIALLY DEFERRED,
  "related_product_id" bigint NULL REFERENCES "techfix_product" ("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS "techfix_solution_category_id_9a5aaa3e"
  ON "techfix_solution" ("category_id");
CREATE INDEX IF NOT EXISTS "techfix_solution_related_product_id_d34e2db7"
  ON "techfix_solution" ("related_product_id");

-- tblinfo (apps.info.Info)
CREATE TABLE IF NOT EXISTS "tblinfo" (
  "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
  "name" varchar(255) NOT NULL,
  "age" integer unsigned NOT NULL CHECK ("age" >= 0),
  "address" varchar(255) NOT NULL,
  "email" varchar(255) NOT NULL,
  "created_at" datetime NOT NULL,
  "updated_at" datetime NOT NULL,
  "user_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS "tblinfo_user_id_4a36749d"
  ON "tblinfo" ("user_id");

PRAGMA foreign_keys = ON;
