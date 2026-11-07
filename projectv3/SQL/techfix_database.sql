-- ============================================================
-- TECHFIX System Database — MySQL / MariaDB
-- Project: projectv3 (Django 6.1.2)
-- Generated: 2026-11-07
-- Engine: InnoDB | Charset: utf8mb4 | Collation: utf8mb4_unicode_ci
--
-- This script mirrors the schema Django creates today for the
-- migrations that are actually installed in this project:
--   contenttypes.0001..0002, auth.0001..0012, admin.0001..0003,
--   sessions.0001, sites.0001..0002,
--   account.0001..0009, socialaccount.0001..0006,
--   core.0001..0008, info.0001, users.0001
--
-- Domain tables (9):
--   1. techfix_category                       (product/accessory/solution grouping)
--   2. techfix_product                        (main tech devices)
--   3. techfix_accessory                      (add-ons: cases, chargers, etc.)
--   4. techfix_accessory_compatible_products  (M:N junction)
--   5. techfix_solution                       (troubleshooting guides / fixes)
--   6. techfix_review                         (customer ratings and feedback)
--   7. techfix_recent_activity                (dashboard activity log)
--   8. users_phoneprofile                     (one-to-one phone number per user)
--   9. tblinfo                                (apps.info.Info + owner)
--
-- Supporting tables (17):
--   django_migrations, django_content_type, django_site, auth_permission,
--   auth_group, auth_user, auth_group_permissions, auth_user_groups,
--   auth_user_user_permissions, django_admin_log, django_session,
--   account_emailaddress, account_emailconfirmation,
--   socialaccount_socialaccount, socialaccount_socialapp,
--   socialaccount_socialapp_sites, socialaccount_socialtoken
--
-- Relationships (ORM on_delete=; Django enforces these in Python):
--   Category 1—N Product      (SET_NULL)
--   Category 1—N Accessory    (SET_NULL)
--   Category 1—N Solution     (SET_NULL)
--   Product  1—N Solution     (SET_NULL)
--   Product  1—N Review       (CASCADE)
--   Accessory 1—N Review      (CASCADE)
--   User     1—N Review       (CASCADE)
--   User     1—1 PhoneProfile (CASCADE, unique)
--   User     1—N RecentActivity (CASCADE)
--   Product  M—N Accessory    (via junction, CASCADE)
--   User     1—N Info         (CASCADE)
--
-- MySQL notes:
--   * JSON columns are native JSON (Django's MySQL JSONField mapping).
--   * MySQL/MariaDB do not support partial (conditional) unique indexes,
--     so Django silently skips these four constraints on MySQL:
--       account_emailaddress.unique_primary_email
--       account_emailaddress.unique_verified_email
--       techfix_review.unique_user_product
--       techfix_review.unique_user_accessory
--     They are still enforced by Django validation and exist on SQLite.
--   * CHECK constraints are enforced on MySQL 8.0.16+ / MariaDB 10.2+.
--
-- IMPORTANT: This is a schema snapshot for a fresh/empty database.
-- For a normal install prefer `python manage.py migrate`.
-- If you imported this script manually, run once:
--   python manage.py migrate --fake
-- so Django records the migrations in django_migrations.
-- ============================================================

CREATE DATABASE IF NOT EXISTS `techfix_db`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `techfix_db`;

SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- Django framework tables
-- ============================================================

-- ------------------------------------------------------------
-- Table: django_migrations
-- Records which migrations Django has applied.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `django_migrations` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `app` VARCHAR(255) NOT NULL,
  `name` VARCHAR(255) NOT NULL,
  `applied` DATETIME(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: django_content_type
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `django_content_type` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `app_label` VARCHAR(100) NOT NULL,
  `model` VARCHAR(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_django_content_type_app_model` (`app_label`, `model`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: auth_permission
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `auth_permission` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `content_type_id` INT NOT NULL,
  `codename` VARCHAR(100) NOT NULL,
  `name` VARCHAR(255) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_auth_permission_content_type_codename` (`content_type_id`, `codename`),
  KEY `idx_auth_permission_content_type` (`content_type_id`),
  CONSTRAINT `fk_permission_content_type`
    FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: auth_group
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `auth_group` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(150) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_auth_group_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: auth_user (Django's default user, used by apps.users)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `auth_user` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `password` VARCHAR(128) NOT NULL,
  `last_login` DATETIME(6) NULL DEFAULT NULL,
  `is_superuser` TINYINT(1) NOT NULL,
  `username` VARCHAR(150) NOT NULL,
  `first_name` VARCHAR(150) NOT NULL,
  `last_name` VARCHAR(150) NOT NULL,
  `email` VARCHAR(254) NOT NULL,
  `is_staff` TINYINT(1) NOT NULL,
  `is_active` TINYINT(1) NOT NULL,
  `date_joined` DATETIME(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_auth_user_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: auth_group_permissions (M:N group <-> permission)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `auth_group_permissions` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `group_id` INT NOT NULL,
  `permission_id` INT NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_auth_group_permissions_group_permission` (`group_id`, `permission_id`),
  KEY `idx_auth_group_permissions_group` (`group_id`),
  KEY `idx_auth_group_permissions_permission` (`permission_id`),
  CONSTRAINT `fk_group_permissions_group`
    FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`),
  CONSTRAINT `fk_group_permissions_permission`
    FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: auth_user_groups (M:N user <-> group)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `auth_user_groups` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `group_id` INT NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_auth_user_groups_user_group` (`user_id`, `group_id`),
  KEY `idx_auth_user_groups_user` (`user_id`),
  KEY `idx_auth_user_groups_group` (`group_id`),
  CONSTRAINT `fk_user_groups_user`
    FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `fk_user_groups_group`
    FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: auth_user_user_permissions (M:N user <-> permission)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `auth_user_user_permissions` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `permission_id` INT NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_auth_user_user_permissions_user_permission` (`user_id`, `permission_id`),
  KEY `idx_auth_user_user_permissions_user` (`user_id`),
  KEY `idx_auth_user_user_permissions_permission` (`permission_id`),
  CONSTRAINT `fk_user_user_permissions_user`
    FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `fk_user_user_permissions_permission`
    FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: django_admin_log
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `django_admin_log` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `object_id` LONGTEXT NULL,
  `object_repr` VARCHAR(200) NOT NULL,
  `action_flag` SMALLINT UNSIGNED NOT NULL,
  `change_message` LONGTEXT NOT NULL,
  `content_type_id` INT NULL DEFAULT NULL,
  `user_id` INT NOT NULL,
  `action_time` DATETIME(6) NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `chk_admin_log_action_flag` CHECK (`action_flag` >= 0),
  KEY `idx_admin_log_content_type` (`content_type_id`),
  KEY `idx_admin_log_user` (`user_id`),
  CONSTRAINT `fk_admin_log_content_type`
    FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`),
  CONSTRAINT `fk_admin_log_user`
    FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: django_session
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `django_session` (
  `session_key` VARCHAR(40) NOT NULL,
  `session_data` LONGTEXT NOT NULL,
  `expire_date` DATETIME(6) NOT NULL,
  PRIMARY KEY (`session_key`),
  KEY `idx_session_expire_date` (`expire_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: django_site (django.contrib.sites; used by allauth, SITE_ID=1)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `django_site` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(50) NOT NULL,
  `domain` VARCHAR(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_django_site_domain` (`domain`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- django-allauth tables (account + socialaccount)
-- ============================================================

-- ------------------------------------------------------------
-- Table: account_emailaddress
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `account_emailaddress` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `verified` TINYINT(1) NOT NULL,
  `primary` TINYINT(1) NOT NULL,
  `user_id` INT NOT NULL,
  `email` VARCHAR(254) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_account_emailaddress_user_email` (`user_id`, `email`),
  KEY `idx_account_emailaddress_email` (`email`),
  KEY `idx_account_emailaddress_user` (`user_id`),
  CONSTRAINT `fk_account_emailaddress_user`
    FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: account_emailconfirmation
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `account_emailconfirmation` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `created` DATETIME(6) NOT NULL,
  `sent` DATETIME(6) NULL DEFAULT NULL,
  `key` VARCHAR(64) NOT NULL,
  `email_address_id` INT NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_account_emailconfirmation_key` (`key`),
  KEY `idx_account_emailconfirmation_email_address` (`email_address_id`),
  CONSTRAINT `fk_account_emailconfirmation_email_address`
    FOREIGN KEY (`email_address_id`) REFERENCES `account_emailaddress` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: socialaccount_socialaccount
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `socialaccount_socialaccount` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `provider` VARCHAR(200) NOT NULL,
  `uid` VARCHAR(191) NOT NULL,
  `last_login` DATETIME(6) NOT NULL,
  `date_joined` DATETIME(6) NOT NULL,
  `user_id` INT NOT NULL,
  `extra_data` JSON NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_socialaccount_provider_uid` (`provider`, `uid`),
  KEY `idx_socialaccount_user` (`user_id`),
  CONSTRAINT `fk_socialaccount_user`
    FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: socialaccount_socialapp
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `socialaccount_socialapp` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `provider` VARCHAR(30) NOT NULL,
  `name` VARCHAR(40) NOT NULL,
  `client_id` VARCHAR(191) NOT NULL,
  `secret` VARCHAR(191) NOT NULL,
  `key` VARCHAR(191) NOT NULL,
  `provider_id` VARCHAR(200) NOT NULL,
  `settings` JSON NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: socialaccount_socialapp_sites (M:N app <-> site)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `socialaccount_socialapp_sites` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `socialapp_id` INT NOT NULL,
  `site_id` INT NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_socialaccount_socialapp_sites_app_site` (`socialapp_id`, `site_id`),
  KEY `idx_socialaccount_socialapp_sites_app` (`socialapp_id`),
  KEY `idx_socialaccount_socialapp_sites_site` (`site_id`),
  CONSTRAINT `fk_socialaccount_socialapp_sites_app`
    FOREIGN KEY (`socialapp_id`) REFERENCES `socialaccount_socialapp` (`id`),
  CONSTRAINT `fk_socialaccount_socialapp_sites_site`
    FOREIGN KEY (`site_id`) REFERENCES `django_site` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: socialaccount_socialtoken
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `socialaccount_socialtoken` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `token` LONGTEXT NOT NULL,
  `token_secret` LONGTEXT NOT NULL,
  `expires_at` DATETIME(6) NULL DEFAULT NULL,
  `account_id` INT NOT NULL,
  `app_id` INT NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_socialaccount_socialtoken_app_account` (`app_id`, `account_id`),
  KEY `idx_socialaccount_socialtoken_account` (`account_id`),
  KEY `idx_socialaccount_socialtoken_app` (`app_id`),
  CONSTRAINT `fk_socialaccount_socialtoken_account`
    FOREIGN KEY (`account_id`) REFERENCES `socialaccount_socialaccount` (`id`),
  CONSTRAINT `fk_socialaccount_socialtoken_app`
    FOREIGN KEY (`app_id`) REFERENCES `socialaccount_socialapp` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- Application tables (apps.core / apps.users / apps.info)
-- ============================================================

-- ------------------------------------------------------------
-- Table: techfix_category
-- Groups products, accessories and solutions (ex. Laptops, Audio)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `techfix_category` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(100) NOT NULL,
  `description` LONGTEXT NOT NULL,
  `created_at` DATETIME(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_techfix_category_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: techfix_product
-- Main technology devices (laptop, phone, printer, router)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `techfix_product` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(255) NOT NULL,
  `brand` VARCHAR(100) NOT NULL,
  `description` LONGTEXT NOT NULL,
  `specifications` LONGTEXT NOT NULL COMMENT 'RAM, CPU, Storage, etc.',
  `price` DECIMAL(10,2) NULL DEFAULT NULL,
  `stock_quantity` INT UNSIGNED NULL DEFAULT NULL,
  `image` VARCHAR(100) NULL DEFAULT NULL COMMENT 'upload_to=products/',
  `created_at` DATETIME(6) NOT NULL,
  `updated_at` DATETIME(6) NOT NULL,
  `category_id` BIGINT NULL DEFAULT NULL,
  `source_url` VARCHAR(200) NOT NULL,
  `online_rating` DECIMAL(3,2) NULL DEFAULT NULL,
  `online_rating_count` INT UNSIGNED NULL DEFAULT NULL,
  `online_rating_source` VARCHAR(100) NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `chk_product_stock_quantity` CHECK (`stock_quantity` >= 0),
  CONSTRAINT `chk_product_online_rating_count` CHECK (`online_rating_count` >= 0),
  KEY `idx_product_category` (`category_id`),
  CONSTRAINT `fk_product_category`
    FOREIGN KEY (`category_id`) REFERENCES `techfix_category` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: techfix_accessory
-- Add-ons: cases, chargers, keyboards, earbuds, cables
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `techfix_accessory` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(255) NOT NULL,
  `brand` VARCHAR(100) NOT NULL,
  `description` LONGTEXT NOT NULL,
  `price` DECIMAL(10,2) NULL DEFAULT NULL,
  `compatibility_notes` LONGTEXT NOT NULL COMMENT 'Ex. Compatible with USB-C laptops',
  `stock_quantity` INT UNSIGNED NULL DEFAULT NULL,
  `image` VARCHAR(100) NULL DEFAULT NULL COMMENT 'upload_to=accessories/',
  `created_at` DATETIME(6) NOT NULL,
  `category_id` BIGINT NULL DEFAULT NULL,
  `source_url` VARCHAR(200) NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `chk_accessory_stock_quantity` CHECK (`stock_quantity` >= 0),
  KEY `idx_accessory_category` (`category_id`),
  CONSTRAINT `fk_accessory_category`
    FOREIGN KEY (`category_id`) REFERENCES `techfix_category` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: techfix_accessory_compatible_products (M:N junction)
-- Which accessories work with which products.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `techfix_accessory_compatible_products` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `accessory_id` BIGINT NOT NULL,
  `product_id` BIGINT NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_accessory_product` (`accessory_id`, `product_id`),
  KEY `idx_junction_accessory` (`accessory_id`),
  KEY `idx_junction_product` (`product_id`),
  CONSTRAINT `fk_junction_accessory`
    FOREIGN KEY (`accessory_id`) REFERENCES `techfix_accessory` (`id`),
  CONSTRAINT `fk_junction_product`
    FOREIGN KEY (`product_id`) REFERENCES `techfix_product` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: techfix_solution
-- Step-by-step fix for a common technology problem.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `techfix_solution` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `title` VARCHAR(255) NOT NULL,
  `problem_description` LONGTEXT NOT NULL COMMENT 'Symptoms / common issue',
  `steps` LONGTEXT NOT NULL COMMENT 'Step 1, Step 2, ...',
  `difficulty_level` VARCHAR(10) NOT NULL,
  `video_url` VARCHAR(200) NOT NULL,
  `created_at` DATETIME(6) NOT NULL,
  `updated_at` DATETIME(6) NOT NULL,
  `category_id` BIGINT NULL DEFAULT NULL,
  `related_product_id` BIGINT NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_solution_category` (`category_id`),
  KEY `idx_solution_product` (`related_product_id`),
  CONSTRAINT `fk_solution_category`
    FOREIGN KEY (`category_id`) REFERENCES `techfix_category` (`id`),
  CONSTRAINT `fk_solution_product`
    FOREIGN KEY (`related_product_id`) REFERENCES `techfix_product` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: techfix_review
-- Rating and feedback for a product OR an accessory (exactly one).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `techfix_review` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `rating` SMALLINT UNSIGNED NOT NULL,
  `title` VARCHAR(120) NOT NULL,
  `comment` LONGTEXT NOT NULL,
  `created_at` DATETIME(6) NOT NULL,
  `updated_at` DATETIME(6) NOT NULL,
  `accessory_id` BIGINT NULL DEFAULT NULL,
  `product_id` BIGINT NULL DEFAULT NULL,
  `user_id` INT NOT NULL,
  `is_sample` TINYINT(1) NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `chk_review_rating` CHECK (`rating` >= 0),
  CONSTRAINT `techfix_review_exactly_one_item` CHECK (
    (`accessory_id` IS NULL AND `product_id` IS NOT NULL)
    OR (`accessory_id` IS NOT NULL AND `product_id` IS NULL)
  ),
  KEY `idx_review_accessory` (`accessory_id`),
  KEY `idx_review_product` (`product_id`),
  KEY `idx_review_user` (`user_id`),
  CONSTRAINT `fk_review_accessory`
    FOREIGN KEY (`accessory_id`) REFERENCES `techfix_accessory` (`id`),
  CONSTRAINT `fk_review_product`
    FOREIGN KEY (`product_id`) REFERENCES `techfix_product` (`id`),
  CONSTRAINT `fk_review_user`
    FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: techfix_recent_activity
-- Per-user dashboard activity, including optional chat history (JSON).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `techfix_recent_activity` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `kind` VARCHAR(40) NOT NULL,
  `title` VARCHAR(120) NOT NULL,
  `url` VARCHAR(2048) NOT NULL,
  `created_at` DATETIME(6) NOT NULL,
  `user_id` INT NOT NULL,
  `chat_history` JSON NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_recent_activity_user` (`user_id`),
  CONSTRAINT `fk_recent_activity_user`
    FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: users_phoneprofile
-- One phone number per user (OneToOne, phone number unique).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `users_phoneprofile` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `phone_number` VARCHAR(16) NULL DEFAULT NULL,
  `user_id` INT NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_users_phoneprofile_phone_number` (`phone_number`),
  UNIQUE KEY `uq_users_phoneprofile_user` (`user_id`),
  CONSTRAINT `fk_phoneprofile_user`
    FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: tblinfo (apps.info.Info)
-- Personal info records, privately owned per user.
-- Superusers see all; regular users see only their own.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `tblinfo` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(255) NOT NULL,
  `age` INT UNSIGNED NOT NULL,
  `address` VARCHAR(255) NOT NULL,
  `email` VARCHAR(255) NOT NULL,
  `created_at` DATETIME(6) NOT NULL,
  `updated_at` DATETIME(6) NOT NULL,
  `user_id` INT NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `chk_tblinfo_age` CHECK (`age` >= 0),
  KEY `idx_tblinfo_user` (`user_id`),
  CONSTRAINT `fk_tblinfo_user`
    FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;

-- ------------------------------------------------------------
-- Default site row (required by django.contrib.sites / allauth,
-- SITE_ID = 1). `python manage.py migrate --fake` also creates it.
-- ------------------------------------------------------------
INSERT IGNORE INTO `django_site` (`id`, `name`, `domain`)
VALUES (1, 'example.com', 'example.com');
