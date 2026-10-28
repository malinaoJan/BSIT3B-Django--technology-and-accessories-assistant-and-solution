-- ============================================================
-- TECHFIX System Database — MySQL / MariaDB
-- Project: projectv3 (Django 6.1.2: apps.core + apps.info + Django built-ins)
-- Generated: 2026-10-28
-- Engine: InnoDB | Charset: utf8mb4 | Collation: utf8mb4_unicode_ci
--
-- This script mirrors the schema Django creates today for the
-- migrations that are actually installed in this project:
--   contenttypes.0001, auth.0001..0012, admin.0001..0003,
--   sessions.0001, core.0001_initial, info.0001_initial.
--
-- Domain tables (apps):
--   1. techfix_category                       (product/accessory/solution grouping)
--   2. techfix_product                        (main tech devices)
--   3. techfix_accessory                      (add-ons: cases, chargers, etc.)
--   4. techfix_accessory_compatible_products  (M:N junction)
--   5. techfix_solution                       (troubleshooting guides / fixes)
--   6. tblinfo                                (apps.info.Info + owner)
--
-- Supporting Django tables (required to run the system):
--   django_migrations, django_content_type, auth_permission, auth_group,
--   auth_user, auth_group_permissions, auth_user_groups,
--   auth_user_user_permissions, django_admin_log, django_session
--
-- Relationships (ORM on_delete=; Django enforces these in Python):
--   Category 1—N Product      (SET_NULL)
--   Category 1—N Accessory    (SET_NULL)
--   Category 1—N Solution     (SET_NULL)
--   Product  1—N Solution     (SET_NULL)
--   Product  M—N Accessory    (via junction, CASCADE)
--   User     1—N Info         (CASCADE)
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
  `id` BIGINT NOT NULL AUTO_INCREMENT,
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
  `id` BIGINT NOT NULL AUTO_INCREMENT,
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
  `id` BIGINT NOT NULL AUTO_INCREMENT,
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

-- ============================================================
-- Application tables (apps.core / apps.info)
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
  `price` DECIMAL(10,2) NOT NULL,
  `stock_quantity` INT UNSIGNED NOT NULL,
  `image` VARCHAR(100) NULL DEFAULT NULL COMMENT 'upload_to=products/',
  `created_at` DATETIME(6) NOT NULL,
  `updated_at` DATETIME(6) NOT NULL,
  `category_id` BIGINT NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `chk_product_stock_quantity` CHECK (`stock_quantity` >= 0),
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
  `price` DECIMAL(10,2) NOT NULL,
  `compatibility_notes` LONGTEXT NOT NULL COMMENT 'Ex. Compatible with USB-C laptops',
  `stock_quantity` INT UNSIGNED NOT NULL,
  `image` VARCHAR(100) NULL DEFAULT NULL COMMENT 'upload_to=accessories/',
  `created_at` DATETIME(6) NOT NULL,
  `category_id` BIGINT NULL DEFAULT NULL,
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
-- Sample seed (optional — comment out if not needed)
-- ------------------------------------------------------------
-- INSERT INTO `techfix_category` (`name`, `description`, `created_at`)
-- VALUES ('Laptops','Laptop devices and related guides', NOW(6)),
--        ('Audio','Headsets, earbuds, speakers', NOW(6)),
--        ('Chargers','Chargers, cables and power accessories', NOW(6));
