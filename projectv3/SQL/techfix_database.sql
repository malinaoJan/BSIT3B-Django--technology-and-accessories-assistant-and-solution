-- ============================================================
-- TECHFIX System Database — MySQL / MariaDB
-- Project: projectv3 (Django: apps.core + apps.info + auth)
-- Generated: 2026-10-16
-- Engine: InnoDB | Charset: utf8mb4
--
-- Entities:
--   1. auth_user                          (Django default user)
--   2. techfix_category                   (product/accessory/solution grouping)
--   3. techfix_product                    (main tech devices)
--   4. techfix_accessory                  (add-ons: cases, chargers, etc.)
--   5. techfix_accessory_compatible_products (M:N junction)
--   6. techfix_solution                   (troubleshooting guides / fixes)
--   7. tblinfo                            (Info: name/age/address/email + owner)
--
-- Relationships:
--   Category 1—N Product      (techfix_product.category_id -> SET NULL)
--   Category 1—N Accessory    (techfix_accessory.category_id -> SET NULL)
--   Category 1—N Solution     (techfix_solution.category_id -> SET NULL)
--   Product  1—N Solution     (techfix_solution.related_product_id -> SET NULL)
--   Product  M—N Accessory    (via techfix_accessory_compatible_products -> CASCADE)
--   User     1—N Info         (tblinfo.user_id -> CASCADE)
-- ============================================================

CREATE DATABASE IF NOT EXISTS `techfix_db`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `techfix_db`;

SET FOREIGN_KEY_CHECKS = 0;

-- ------------------------------------------------------------
-- Table: auth_user (Django's default user, used by apps.users)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `auth_user` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `password` VARCHAR(128) NOT NULL,
  `last_login` DATETIME(6) NULL DEFAULT NULL,
  `is_superuser` TINYINT(1) NOT NULL DEFAULT 0,
  `username` VARCHAR(150) NOT NULL,
  `first_name` VARCHAR(150) NOT NULL DEFAULT '',
  `last_name` VARCHAR(150) NOT NULL DEFAULT '',
  `email` VARCHAR(254) NOT NULL DEFAULT '',
  `is_staff` TINYINT(1) NOT NULL DEFAULT 0,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `date_joined` DATETIME(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_auth_user_username` (`username`),
  KEY `idx_auth_user_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: techfix_category
-- Groups products, accessories and solutions (ex. Laptops, Audio)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `techfix_category` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(100) NOT NULL,
  `description` TEXT NOT NULL,
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
  `category_id` BIGINT NULL DEFAULT NULL,
  `brand` VARCHAR(100) NOT NULL DEFAULT '',
  `description` TEXT NOT NULL,
  `specifications` TEXT NOT NULL COMMENT 'RAM, CPU, Storage, etc.',
  `price` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  `stock_quantity` INT UNSIGNED NOT NULL DEFAULT 0,
  `image` VARCHAR(100) NULL DEFAULT NULL COMMENT 'upload_to=products/',
  `created_at` DATETIME(6) NOT NULL,
  `updated_at` DATETIME(6) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_product_category` (`category_id`),
  KEY `idx_product_name` (`name`),
  CONSTRAINT `fk_product_category`
    FOREIGN KEY (`category_id`) REFERENCES `techfix_category` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: techfix_accessory
-- Add-ons: cases, chargers, keyboards, earbuds, cables
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `techfix_accessory` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(255) NOT NULL,
  `category_id` BIGINT NULL DEFAULT NULL,
  `brand` VARCHAR(100) NOT NULL DEFAULT '',
  `description` TEXT NOT NULL,
  `price` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  `compatibility_notes` TEXT NOT NULL COMMENT 'Ex. Compatible with USB-C laptops',
  `stock_quantity` INT UNSIGNED NOT NULL DEFAULT 0,
  `image` VARCHAR(100) NULL DEFAULT NULL COMMENT 'upload_to=accessories/',
  `created_at` DATETIME(6) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_accessory_category` (`category_id`),
  KEY `idx_accessory_name` (`name`),
  CONSTRAINT `fk_accessory_category`
    FOREIGN KEY (`category_id`) REFERENCES `techfix_category` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
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
    FOREIGN KEY (`accessory_id`) REFERENCES `techfix_accessory` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_junction_product`
    FOREIGN KEY (`product_id`) REFERENCES `techfix_product` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Table: techfix_solution
-- Step-by-step fix for a common technology problem.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `techfix_solution` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `title` VARCHAR(255) NOT NULL,
  `problem_description` TEXT NOT NULL COMMENT 'Symptoms / common issue',
  `steps` TEXT NOT NULL COMMENT 'Step 1, Step 2, ...',
  `difficulty_level` VARCHAR(10) NOT NULL DEFAULT 'Easy',
  `category_id` BIGINT NULL DEFAULT NULL,
  `related_product_id` BIGINT NULL DEFAULT NULL,
  `video_url` VARCHAR(200) NOT NULL DEFAULT '',
  `created_at` DATETIME(6) NOT NULL,
  `updated_at` DATETIME(6) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_solution_category` (`category_id`),
  KEY `idx_solution_product` (`related_product_id`),
  KEY `idx_solution_difficulty` (`difficulty_level`),
  CONSTRAINT `chk_solution_difficulty`
    CHECK (`difficulty_level` IN ('Easy','Medium','Hard')),
  CONSTRAINT `fk_solution_category`
    FOREIGN KEY (`category_id`) REFERENCES `techfix_category` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_solution_product`
    FOREIGN KEY (`related_product_id`) REFERENCES `techfix_product` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
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
  `email` VARCHAR(255) NOT NULL DEFAULT '',
  `user_id` INT NULL DEFAULT NULL,
  `created_at` DATETIME(6) NOT NULL,
  `updated_at` DATETIME(6) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_tblinfo_user` (`user_id`),
  KEY `idx_tblinfo_name` (`name`),
  CONSTRAINT `chk_tblinfo_age` CHECK (`age` BETWEEN 1 AND 150),
  CONSTRAINT `fk_tblinfo_user`
    FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

SET FOREIGN_KEY_CHECKS = 1;

-- ------------------------------------------------------------
-- Sample seed (optional — comment out if not needed)
-- ------------------------------------------------------------
-- INSERT INTO `techfix_category` (`name`, `description`, `created_at`)
-- VALUES ('Laptops','Laptop devices and related guides', NOW(6)),
--        ('Audio','Headsets, earbuds, speakers', NOW(6)),
--        ('Chargers','Chargers, cables and power accessories', NOW(6));
