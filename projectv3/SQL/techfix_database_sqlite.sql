-- ============================================================
-- TECHFIX System Database - SQLite
-- Project: projectv3 (Django 6.1.2)
-- Generated: 2026-11-11
--
-- Exact schema Django creates today via:
--   python manage.py migrate
--
-- Migrations mirrored:
--   contenttypes.0001..0002, auth.0001..0012, admin.0001..0003,
--   sessions.0001, sites.0001..0002,
--   account.0001..0009, socialaccount.0001..0006,
--   core.0001..0008, info.0001, users.0001
--
-- Domain tables (9):
--   techfix_category, techfix_product, techfix_accessory,
--   techfix_accessory_compatible_products, techfix_solution,
--   techfix_review, techfix_recent_activity, users_phoneprofile, tblinfo
--
-- Supporting tables (17):
--   django_migrations, django_content_type, django_site, auth_permission,
--   auth_group, auth_user, auth_group_permissions, auth_user_groups,
--   auth_user_user_permissions, django_admin_log, django_session,
--   account_emailaddress, account_emailconfirmation,
--   socialaccount_socialaccount, socialaccount_socialapp,
--   socialaccount_socialapp_sites, socialaccount_socialtoken
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

CREATE TABLE IF NOT EXISTS "account_emailaddress" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "verified" bool NOT NULL, "primary" bool NOT NULL, "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "email" varchar(254) NOT NULL);

CREATE TABLE IF NOT EXISTS "account_emailconfirmation" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "created" datetime NOT NULL, "sent" datetime NULL, "key" varchar(64) NOT NULL UNIQUE, "email_address_id" integer NOT NULL REFERENCES "account_emailaddress" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE IF NOT EXISTS "auth_group" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(150) NOT NULL UNIQUE);

CREATE TABLE IF NOT EXISTS "auth_group_permissions" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "group_id" integer NOT NULL REFERENCES "auth_group" ("id") DEFERRABLE INITIALLY DEFERRED, "permission_id" integer NOT NULL REFERENCES "auth_permission" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE IF NOT EXISTS "auth_permission" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "content_type_id" integer NOT NULL REFERENCES "django_content_type" ("id") DEFERRABLE INITIALLY DEFERRED, "codename" varchar(100) NOT NULL, "name" varchar(255) NOT NULL);

CREATE TABLE IF NOT EXISTS "auth_user" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "password" varchar(128) NOT NULL, "last_login" datetime NULL, "is_superuser" bool NOT NULL, "username" varchar(150) NOT NULL UNIQUE, "last_name" varchar(150) NOT NULL, "email" varchar(254) NOT NULL, "is_staff" bool NOT NULL, "is_active" bool NOT NULL, "date_joined" datetime NOT NULL, "first_name" varchar(150) NOT NULL);

CREATE TABLE IF NOT EXISTS "auth_user_groups" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "group_id" integer NOT NULL REFERENCES "auth_group" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE IF NOT EXISTS "auth_user_user_permissions" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "permission_id" integer NOT NULL REFERENCES "auth_permission" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE IF NOT EXISTS "django_admin_log" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "object_id" text NULL, "object_repr" varchar(200) NOT NULL, "action_flag" smallint unsigned NOT NULL CHECK ("action_flag" >= 0), "change_message" text NOT NULL, "content_type_id" integer NULL REFERENCES "django_content_type" ("id") DEFERRABLE INITIALLY DEFERRED, "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "action_time" datetime NOT NULL);

CREATE TABLE IF NOT EXISTS "django_content_type" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "app_label" varchar(100) NOT NULL, "model" varchar(100) NOT NULL);

CREATE TABLE IF NOT EXISTS "django_migrations" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "app" varchar(255) NOT NULL, "name" varchar(255) NOT NULL, "applied" datetime NOT NULL);

CREATE TABLE IF NOT EXISTS "django_session" ("session_key" varchar(40) NOT NULL PRIMARY KEY, "session_data" text NOT NULL, "expire_date" datetime NOT NULL);

CREATE TABLE IF NOT EXISTS "django_site" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(50) NOT NULL, "domain" varchar(100) NOT NULL UNIQUE);

CREATE TABLE IF NOT EXISTS "socialaccount_socialaccount" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "provider" varchar(200) NOT NULL, "uid" varchar(191) NOT NULL, "last_login" datetime NOT NULL, "date_joined" datetime NOT NULL, "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "extra_data" text NOT NULL CHECK ((JSON_VALID("extra_data") OR "extra_data" IS NULL)));

CREATE TABLE IF NOT EXISTS "socialaccount_socialapp" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "provider" varchar(30) NOT NULL, "name" varchar(40) NOT NULL, "client_id" varchar(191) NOT NULL, "secret" varchar(191) NOT NULL, "key" varchar(191) NOT NULL, "provider_id" varchar(200) NOT NULL, "settings" text NOT NULL CHECK ((JSON_VALID("settings") OR "settings" IS NULL)));

CREATE TABLE IF NOT EXISTS "socialaccount_socialapp_sites" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "socialapp_id" integer NOT NULL REFERENCES "socialaccount_socialapp" ("id") DEFERRABLE INITIALLY DEFERRED, "site_id" integer NOT NULL REFERENCES "django_site" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE IF NOT EXISTS "socialaccount_socialtoken" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "token" text NOT NULL, "token_secret" text NOT NULL, "expires_at" datetime NULL, "account_id" integer NOT NULL REFERENCES "socialaccount_socialaccount" ("id") DEFERRABLE INITIALLY DEFERRED, "app_id" integer NULL REFERENCES "socialaccount_socialapp" ("id") DEFERRABLE INITIALLY DEFERRED);

-- ============================================================
-- TECHFIX application tables
-- ============================================================

CREATE TABLE IF NOT EXISTS "tblinfo" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(255) NOT NULL, "age" integer unsigned NOT NULL CHECK ("age" >= 0), "address" varchar(255) NOT NULL, "email" varchar(255) NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "user_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE IF NOT EXISTS "techfix_accessory" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(255) NOT NULL, "brand" varchar(100) NOT NULL, "description" text NOT NULL, "price" decimal NULL, "compatibility_notes" text NOT NULL, "image" varchar(100) NULL, "created_at" datetime NOT NULL, "category_id" bigint NULL REFERENCES "techfix_category" ("id") DEFERRABLE INITIALLY DEFERRED, "source_url" varchar(200) NOT NULL, "stock_quantity" integer unsigned NULL CHECK ("stock_quantity" >= 0));

CREATE TABLE IF NOT EXISTS "techfix_accessory_compatible_products" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "accessory_id" bigint NOT NULL REFERENCES "techfix_accessory" ("id") DEFERRABLE INITIALLY DEFERRED, "product_id" bigint NOT NULL REFERENCES "techfix_product" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE IF NOT EXISTS "techfix_category" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(100) NOT NULL UNIQUE, "description" text NOT NULL, "created_at" datetime NOT NULL);

CREATE TABLE IF NOT EXISTS "techfix_product" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(255) NOT NULL, "brand" varchar(100) NOT NULL, "description" text NOT NULL, "specifications" text NOT NULL, "price" decimal NULL, "stock_quantity" integer unsigned NULL CHECK ("stock_quantity" >= 0), "image" varchar(100) NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "category_id" bigint NULL REFERENCES "techfix_category" ("id") DEFERRABLE INITIALLY DEFERRED, "source_url" varchar(200) NOT NULL, "online_rating" decimal NULL, "online_rating_count" integer unsigned NULL CHECK ("online_rating_count" >= 0), "online_rating_source" varchar(100) NOT NULL);

CREATE TABLE IF NOT EXISTS "techfix_recent_activity" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "kind" varchar(40) NOT NULL, "title" varchar(120) NOT NULL, "url" varchar(2048) NOT NULL, "created_at" datetime NOT NULL, "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "chat_history" text NOT NULL CHECK ((JSON_VALID("chat_history") OR "chat_history" IS NULL)));

CREATE TABLE IF NOT EXISTS "techfix_review" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "rating" smallint unsigned NOT NULL CHECK ("rating" >= 0), "title" varchar(120) NOT NULL, "comment" text NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "accessory_id" bigint NULL REFERENCES "techfix_accessory" ("id") DEFERRABLE INITIALLY DEFERRED, "product_id" bigint NULL REFERENCES "techfix_product" ("id") DEFERRABLE INITIALLY DEFERRED, "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "is_sample" bool NOT NULL, CONSTRAINT "techfix_review_exactly_one_item" CHECK ((("accessory_id" IS NULL AND "product_id" IS NOT NULL) OR ("accessory_id" IS NOT NULL AND "product_id" IS NULL))));

CREATE TABLE IF NOT EXISTS "techfix_solution" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "title" varchar(255) NOT NULL, "problem_description" text NOT NULL, "steps" text NOT NULL, "difficulty_level" varchar(10) NOT NULL, "video_url" varchar(200) NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "category_id" bigint NULL REFERENCES "techfix_category" ("id") DEFERRABLE INITIALLY DEFERRED, "related_product_id" bigint NULL REFERENCES "techfix_product" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE IF NOT EXISTS "users_phoneprofile" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "phone_number" varchar(16) NULL UNIQUE, "user_id" integer NOT NULL UNIQUE REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED);

-- ============================================================
-- Indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS "account_emailaddress_email_03be32b2" ON "account_emailaddress" ("email");

CREATE INDEX IF NOT EXISTS "account_emailaddress_user_id_2c513194" ON "account_emailaddress" ("user_id");

CREATE UNIQUE INDEX IF NOT EXISTS "account_emailaddress_user_id_email_987c8728_uniq" ON "account_emailaddress" ("user_id", "email");

CREATE INDEX IF NOT EXISTS "account_emailconfirmation_email_address_id_5b7f8c58" ON "account_emailconfirmation" ("email_address_id");

CREATE INDEX IF NOT EXISTS "auth_group_permissions_group_id_b120cbf9" ON "auth_group_permissions" ("group_id");

CREATE UNIQUE INDEX IF NOT EXISTS "auth_group_permissions_group_id_permission_id_0cd325b0_uniq" ON "auth_group_permissions" ("group_id", "permission_id");

CREATE INDEX IF NOT EXISTS "auth_group_permissions_permission_id_84c5c92e" ON "auth_group_permissions" ("permission_id");

CREATE INDEX IF NOT EXISTS "auth_permission_content_type_id_2f476e4b" ON "auth_permission" ("content_type_id");

CREATE UNIQUE INDEX IF NOT EXISTS "auth_permission_content_type_id_codename_01ab375a_uniq" ON "auth_permission" ("content_type_id", "codename");

CREATE INDEX IF NOT EXISTS "auth_user_groups_group_id_97559544" ON "auth_user_groups" ("group_id");

CREATE INDEX IF NOT EXISTS "auth_user_groups_user_id_6a12ed8b" ON "auth_user_groups" ("user_id");

CREATE UNIQUE INDEX IF NOT EXISTS "auth_user_groups_user_id_group_id_94350c0c_uniq" ON "auth_user_groups" ("user_id", "group_id");

CREATE INDEX IF NOT EXISTS "auth_user_user_permissions_permission_id_1fbb5f2c" ON "auth_user_user_permissions" ("permission_id");

CREATE INDEX IF NOT EXISTS "auth_user_user_permissions_user_id_a95ead1b" ON "auth_user_user_permissions" ("user_id");

CREATE UNIQUE INDEX IF NOT EXISTS "auth_user_user_permissions_user_id_permission_id_14a6b632_uniq" ON "auth_user_user_permissions" ("user_id", "permission_id");

CREATE INDEX IF NOT EXISTS "django_admin_log_content_type_id_c4bce8eb" ON "django_admin_log" ("content_type_id");

CREATE INDEX IF NOT EXISTS "django_admin_log_user_id_c564eba6" ON "django_admin_log" ("user_id");

CREATE UNIQUE INDEX IF NOT EXISTS "django_content_type_app_label_model_76bd3d3b_uniq" ON "django_content_type" ("app_label", "model");

CREATE INDEX IF NOT EXISTS "django_session_expire_date_a5c62663" ON "django_session" ("expire_date");

CREATE UNIQUE INDEX IF NOT EXISTS "socialaccount_socialaccount_provider_uid_fc810c6e_uniq" ON "socialaccount_socialaccount" ("provider", "uid");

CREATE INDEX IF NOT EXISTS "socialaccount_socialaccount_user_id_8146e70c" ON "socialaccount_socialaccount" ("user_id");

CREATE INDEX IF NOT EXISTS "socialaccount_socialapp_sites_site_id_2579dee5" ON "socialaccount_socialapp_sites" ("site_id");

CREATE INDEX IF NOT EXISTS "socialaccount_socialapp_sites_socialapp_id_97fb6e7d" ON "socialaccount_socialapp_sites" ("socialapp_id");

CREATE UNIQUE INDEX IF NOT EXISTS "socialaccount_socialapp_sites_socialapp_id_site_id_71a9a768_uniq" ON "socialaccount_socialapp_sites" ("socialapp_id", "site_id");

CREATE INDEX IF NOT EXISTS "socialaccount_socialtoken_account_id_951f210e" ON "socialaccount_socialtoken" ("account_id");

CREATE INDEX IF NOT EXISTS "socialaccount_socialtoken_app_id_636a42d7" ON "socialaccount_socialtoken" ("app_id");

CREATE UNIQUE INDEX IF NOT EXISTS "socialaccount_socialtoken_app_id_account_id_fca4e0ac_uniq" ON "socialaccount_socialtoken" ("app_id", "account_id");

CREATE INDEX IF NOT EXISTS "tblinfo_user_id_4a36749d" ON "tblinfo" ("user_id");

CREATE INDEX IF NOT EXISTS "techfix_accessory_category_id_fe43e20e" ON "techfix_accessory" ("category_id");

CREATE INDEX IF NOT EXISTS "techfix_accessory_compatible_products_accessory_id_2bdcbf14" ON "techfix_accessory_compatible_products" ("accessory_id");

CREATE UNIQUE INDEX IF NOT EXISTS "techfix_accessory_compatible_products_accessory_id_product_id_f86249ad_uniq" ON "techfix_accessory_compatible_products" ("accessory_id", "product_id");

CREATE INDEX IF NOT EXISTS "techfix_accessory_compatible_products_product_id_10161dcf" ON "techfix_accessory_compatible_products" ("product_id");

CREATE INDEX IF NOT EXISTS "techfix_product_category_id_d7b87187" ON "techfix_product" ("category_id");

CREATE INDEX IF NOT EXISTS "techfix_recent_activity_user_id_2165119d" ON "techfix_recent_activity" ("user_id");

CREATE INDEX IF NOT EXISTS "techfix_review_accessory_id_d92ba363" ON "techfix_review" ("accessory_id");

CREATE INDEX IF NOT EXISTS "techfix_review_product_id_5fda52b0" ON "techfix_review" ("product_id");

CREATE UNIQUE INDEX IF NOT EXISTS "techfix_review_unique_user_accessory" ON "techfix_review" ("user_id", "accessory_id") WHERE "accessory_id" IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS "techfix_review_unique_user_product" ON "techfix_review" ("user_id", "product_id") WHERE "product_id" IS NOT NULL;

CREATE INDEX IF NOT EXISTS "techfix_review_user_id_bd5a99c7" ON "techfix_review" ("user_id");

CREATE INDEX IF NOT EXISTS "techfix_solution_category_id_9a5aaa3e" ON "techfix_solution" ("category_id");

CREATE INDEX IF NOT EXISTS "techfix_solution_related_product_id_d34e2db7" ON "techfix_solution" ("related_product_id");

CREATE UNIQUE INDEX IF NOT EXISTS "unique_primary_email" ON "account_emailaddress" ("user_id", "primary") WHERE "primary" = 1;

CREATE UNIQUE INDEX IF NOT EXISTS "unique_verified_email" ON "account_emailaddress" ("email") WHERE "verified" = 1;

PRAGMA foreign_keys = ON;
