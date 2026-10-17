-- ============================================================
-- TECHFIX System Database — SQLite version
-- Same schema as techfix_database.sql, adapted for SQLite.
-- This matches what Django creates via:
--   python manage.py sqlmigrate core 0001_initial
--   python manage.py sqlmigrate info 0001_initial
--   + Django's built-in auth_user table.
-- To apply: sqlite3 techfix.db < techfix_database_sqlite.sql
-- ============================================================

PRAGMA foreign_keys = OFF;

-- auth_user (Django default)
CREATE TABLE IF NOT EXISTS "auth_user" (
  "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  "password" VARCHAR(128) NOT NULL,
  "last_login" DATETIME NULL,
  "is_superuser" BOOLEAN NOT NULL DEFAULT 0,
  "username" VARCHAR(150) NOT NULL UNIQUE,
  "first_name" VARCHAR(150) NOT NULL DEFAULT '',
  "last_name" VARCHAR(150) NOT NULL DEFAULT '',
  "email" VARCHAR(254) NOT NULL DEFAULT '',
  "is_staff" BOOLEAN NOT NULL DEFAULT 0,
  "is_active" BOOLEAN NOT NULL DEFAULT 1,
  "date_joined" DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS "idx_auth_user_username" ON "auth_user" ("username");

-- techfix_category
CREATE TABLE IF NOT EXISTS "techfix_category" (
  "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  "name" VARCHAR(100) NOT NULL UNIQUE,
  "description" TEXT NOT NULL DEFAULT '',
  "created_at" DATETIME NOT NULL
);

-- techfix_product
CREATE TABLE IF NOT EXISTS "techfix_product" (
  "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  "name" VARCHAR(255) NOT NULL,
  "category_id" BIGINT NULL REFERENCES "techfix_category" ("id") ON DELETE SET NULL,
  "brand" VARCHAR(100) NOT NULL DEFAULT '',
  "description" TEXT NOT NULL DEFAULT '',
  "specifications" TEXT NOT NULL DEFAULT '',
  "price" DECIMAL(10, 2) NOT NULL DEFAULT 0,
  "stock_quantity" INTEGER UNSIGNED NOT NULL DEFAULT 0 CHECK ("stock_quantity" >= 0),
  "image" VARCHAR(100) NULL,
  "created_at" DATETIME NOT NULL,
  "updated_at" DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS "idx_product_category" ON "techfix_product" ("category_id");

-- techfix_accessory
CREATE TABLE IF NOT EXISTS "techfix_accessory" (
  "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  "name" VARCHAR(255) NOT NULL,
  "category_id" BIGINT NULL REFERENCES "techfix_category" ("id") ON DELETE SET NULL,
  "brand" VARCHAR(100) NOT NULL DEFAULT '',
  "description" TEXT NOT NULL DEFAULT '',
  "price" DECIMAL(10, 2) NOT NULL DEFAULT 0,
  "compatibility_notes" TEXT NOT NULL DEFAULT '',
  "stock_quantity" INTEGER UNSIGNED NOT NULL DEFAULT 0 CHECK ("stock_quantity" >= 0),
  "image" VARCHAR(100) NULL,
  "created_at" DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS "idx_accessory_category" ON "techfix_accessory" ("category_id");

-- M:N junction: accessory <-> product
CREATE TABLE IF NOT EXISTS "techfix_accessory_compatible_products" (
  "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  "accessory_id" BIGINT NOT NULL REFERENCES "techfix_accessory" ("id") ON DELETE CASCADE,
  "product_id" BIGINT NOT NULL REFERENCES "techfix_product" ("id") ON DELETE CASCADE,
  UNIQUE ("accessory_id", "product_id")
);
CREATE INDEX IF NOT EXISTS "idx_junction_accessory" ON "techfix_accessory_compatible_products" ("accessory_id");
CREATE INDEX IF NOT EXISTS "idx_junction_product" ON "techfix_accessory_compatible_products" ("product_id");

-- techfix_solution
CREATE TABLE IF NOT EXISTS "techfix_solution" (
  "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  "title" VARCHAR(255) NOT NULL,
  "problem_description" TEXT NOT NULL DEFAULT '',
  "steps" TEXT NOT NULL DEFAULT '',
  "difficulty_level" VARCHAR(10) NOT NULL DEFAULT 'Easy' CHECK ("difficulty_level" IN ('Easy','Medium','Hard')),
  "category_id" BIGINT NULL REFERENCES "techfix_category" ("id") ON DELETE SET NULL,
  "related_product_id" BIGINT NULL REFERENCES "techfix_product" ("id") ON DELETE SET NULL,
  "video_url" VARCHAR(200) NOT NULL DEFAULT '',
  "created_at" DATETIME NOT NULL,
  "updated_at" DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS "idx_solution_category" ON "techfix_solution" ("category_id");
CREATE INDEX IF NOT EXISTS "idx_solution_product" ON "techfix_solution" ("related_product_id");

-- tblinfo (apps.info.Info)
CREATE TABLE IF NOT EXISTS "tblinfo" (
  "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  "name" VARCHAR(255) NOT NULL,
  "age" INTEGER UNSIGNED NOT NULL CHECK ("age" >= 0),
  "address" VARCHAR(255) NOT NULL,
  "email" VARCHAR(255) NOT NULL DEFAULT '',
  "user_id" INTEGER NULL REFERENCES "auth_user" ("id") ON DELETE CASCADE,
  "created_at" DATETIME NOT NULL,
  "updated_at" DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS "idx_tblinfo_user" ON "tblinfo" ("user_id");

PRAGMA foreign_keys = ON;
