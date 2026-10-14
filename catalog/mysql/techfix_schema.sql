-- ============================================================================
-- TECHFIX - Initial Database Table Design (MySQL 8+ / InnoDB)
-- ============================================================================
-- Source: catalog/models.py + catalog/migrations/0001_initial.py
-- Database: techfix
-- Charset: utf8mb4 / utf8mb4_unicode_ci
--
-- Tables (10):
--  1. auth_user (Django default, referenced by AUTH_USER_MODEL)
--  2. catalog_category
--  3. catalog_device
--  4. catalog_product
--  5. catalog_compatibility (product <-> device M:N)
--  6. catalog_userprofile (extends auth_user 1:1)
--  7. catalog_recommendationrequest
--  8. catalog_recommendation (request 1:N products)
--  9. catalog_troubleshootingguide
-- 10. catalog_supportticket
--
-- Relationships:
--  Category 1:N Product (PROTECT / RESTRICT)
--  Product N:M Device via Compatibility (CASCADE)
--  User 1:1 UserProfile (CASCADE)
--  User 1:N RecommendationRequest (SET NULL)
--  Device 1:N RecommendationRequest (SET NULL)
--  RecommendationRequest 1:N Recommendation (CASCADE)
--  Product 1:N Recommendation (CASCADE)
--  User 1:N SupportTicket (SET NULL)
--
-- To use with Django, install mysqlclient and set in core/settings.py:
--   DATABASES = {
--     'default': {
--       'ENGINE': 'django.db.backends.mysql',
--       'NAME': 'techfix',
--       'USER': 'techfix_user',
--       'PASSWORD': 'change-me',
--       'HOST': '127.0.0.1',
--       'PORT': '3306',
--       'OPTIONS': {'charset': 'utf8mb4'},
--     }
--   }
-- ============================================================================

CREATE DATABASE IF NOT EXISTS `techfix`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `techfix`;

-- Clean re-run support: drop child tables first
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS `catalog_recommendation`;
DROP TABLE IF EXISTS `catalog_recommendationrequest`;
DROP TABLE IF EXISTS `catalog_compatibility`;
DROP TABLE IF EXISTS `catalog_userprofile`;
DROP TABLE IF EXISTS `catalog_supportticket`;
DROP TABLE IF EXISTS `catalog_product`;
DROP TABLE IF EXISTS `catalog_device`;
DROP TABLE IF EXISTS `catalog_category`;
DROP TABLE IF EXISTS `catalog_troubleshootingguide`;
-- auth_user is managed by Django auth; only drop if you own it:
-- DROP TABLE IF EXISTS `auth_user`;
SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================================
-- 1. auth_user (Django contrib.auth default)
-- Referenced by UserProfile.user, RecommendationRequest.user, SupportTicket.user
-- In a real Django MySQL migrate this table is auto-created. Included here
-- so FKs resolve when running this file standalone.
-- ============================================================================
CREATE TABLE IF NOT EXISTS `auth_user` (
  `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `password` VARCHAR(128) NOT NULL,
  `last_login` DATETIME(6) NULL,
  `is_superuser` TINYINT(1) NOT NULL DEFAULT 0,
  `username` VARCHAR(150) NOT NULL UNIQUE,
  `first_name` VARCHAR(150) NOT NULL DEFAULT '',
  `last_name` VARCHAR(150) NOT NULL DEFAULT '',
  `email` VARCHAR(254) NOT NULL DEFAULT '',
  `is_staff` TINYINT(1) NOT NULL DEFAULT 0,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `date_joined` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 2. Product categories
-- Django: catalog.Category (name unique)
-- ============================================================================
CREATE TABLE IF NOT EXISTS `catalog_category` (
  `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(100) NOT NULL UNIQUE,
  `description` TEXT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 3. Devices owned / used by customers
-- Django: catalog.Device + UniqueConstraint(brand, model_name)
-- ============================================================================
CREATE TABLE IF NOT EXISTS `catalog_device` (
  `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `brand` VARCHAR(100) NOT NULL,
  `model_name` VARCHAR(160) NOT NULL,
  `device_type` VARCHAR(20) NOT NULL DEFAULT 'phone',
  `connector_type` VARCHAR(80) NOT NULL DEFAULT '',
  `notes` TEXT NOT NULL,
  CONSTRAINT `chk_device_type`
    CHECK (`device_type` IN ('phone','tablet','laptop','desktop','other')),
  UNIQUE KEY `unique_device_model` (`brand`, `model_name`),
  KEY `idx_device_type` (`device_type`),
  KEY `idx_device_brand_model` (`brand`, `model_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 4. Technology products and accessories
-- Django: catalog.Product (category FK PROTECT -> RESTRICT in MySQL)
-- ============================================================================
CREATE TABLE IF NOT EXISTS `catalog_product` (
  `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `category_id` BIGINT NOT NULL,
  `name` VARCHAR(160) NOT NULL,
  `brand` VARCHAR(100) NOT NULL,
  `description` TEXT NOT NULL,
  -- Django JSONField(default=dict, blank=True). MySQL JSON has no DB default,
  -- Django supplies '{}' at the app layer. Keep NOT NULL for parity.
  `specifications` JSON NOT NULL,
  `price` DECIMAL(10,2) NOT NULL,
  `stock_quantity` INT UNSIGNED NOT NULL DEFAULT 0,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT `chk_product_price` CHECK (`price` >= 0),
  CONSTRAINT `fk_product_category`
    FOREIGN KEY (`category_id`)
    REFERENCES `catalog_category` (`id`)
    ON DELETE RESTRICT
    ON UPDATE CASCADE,
  KEY `idx_product_category` (`category_id`),
  KEY `idx_product_active_created` (`is_active`, `created_at`),
  KEY `idx_product_brand_name` (`brand`, `name`),
  KEY `idx_product_price` (`price`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 5. Which products work with which devices (M:N)
-- Django: catalog.Compatibility + UniqueConstraint(product, device)
-- ============================================================================
CREATE TABLE IF NOT EXISTS `catalog_compatibility` (
  `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `product_id` BIGINT NOT NULL,
  `device_id` BIGINT NOT NULL,
  `compatibility_notes` VARCHAR(255) NOT NULL DEFAULT '',
  `verified` TINYINT(1) NOT NULL DEFAULT 0,
  UNIQUE KEY `unique_product_device_compatibility` (`product_id`, `device_id`),
  CONSTRAINT `fk_compat_product`
    FOREIGN KEY (`product_id`)
    REFERENCES `catalog_product` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `fk_compat_device`
    FOREIGN KEY (`device_id`)
    REFERENCES `catalog_device` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  KEY `idx_compat_device` (`device_id`),
  KEY `idx_compat_verified` (`verified`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 6. Additional customer profile information
-- Django: catalog.UserProfile (user OneToOne -> UNIQUE + CASCADE)
-- ============================================================================
CREATE TABLE IF NOT EXISTS `catalog_userprofile` (
  `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `user_id` BIGINT NOT NULL UNIQUE,
  `phone` VARCHAR(30) NOT NULL DEFAULT '',
  `preferred_budget` DECIMAL(10,2) NULL,
  `preferred_device_id` BIGINT NULL,
  CONSTRAINT `fk_profile_user`
    FOREIGN KEY (`user_id`)
    REFERENCES `auth_user` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `fk_profile_device`
    FOREIGN KEY (`preferred_device_id`)
    REFERENCES `catalog_device` (`id`)
    ON DELETE SET NULL
    ON UPDATE CASCADE,
  KEY `idx_profile_device` (`preferred_device_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 7. A customer's product recommendation request
-- Django: catalog.RecommendationRequest (user/device SET_NULL)
-- ============================================================================
CREATE TABLE IF NOT EXISTS `catalog_recommendationrequest` (
  `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `user_id` BIGINT NULL,
  `device_id` BIGINT NULL,
  `intended_use` VARCHAR(160) NOT NULL,
  `budget_min` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  `budget_max` DECIMAL(10,2) NOT NULL,
  `notes` TEXT NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT `chk_req_budget_min` CHECK (`budget_min` >= 0),
  CONSTRAINT `chk_req_budget_max` CHECK (`budget_max` >= 0),
  CONSTRAINT `fk_req_user`
    FOREIGN KEY (`user_id`)
    REFERENCES `auth_user` (`id`)
    ON DELETE SET NULL
    ON UPDATE CASCADE,
  CONSTRAINT `fk_req_device`
    FOREIGN KEY (`device_id`)
    REFERENCES `catalog_device` (`id`)
    ON DELETE SET NULL
    ON UPDATE CASCADE,
  KEY `idx_req_user` (`user_id`),
  KEY `idx_req_device` (`device_id`),
  KEY `idx_req_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 8. Products recommended for each request
-- Django: catalog.Recommendation + UniqueConstraint(request, product)
-- Note: `rank` and `request_id` are quoted because RANK is reserved in MySQL 8.
-- ============================================================================
CREATE TABLE IF NOT EXISTS `catalog_recommendation` (
  `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `request_id` BIGINT NOT NULL,
  `product_id` BIGINT NOT NULL,
  `reason` VARCHAR(255) NOT NULL DEFAULT '',
  `rank` SMALLINT UNSIGNED NOT NULL DEFAULT 1,
  UNIQUE KEY `unique_recommended_product_per_request` (`request_id`, `product_id`),
  CONSTRAINT `fk_reco_request`
    FOREIGN KEY (`request_id`)
    REFERENCES `catalog_recommendationrequest` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `fk_reco_product`
    FOREIGN KEY (`product_id`)
    REFERENCES `catalog_product` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  KEY `idx_reco_product` (`product_id`),
  KEY `idx_reco_rank` (`rank`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 9. Troubleshooting articles and solutions
-- Django: catalog.TroubleshootingGuide
-- ============================================================================
CREATE TABLE IF NOT EXISTS `catalog_troubleshootingguide` (
  `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `title` VARCHAR(180) NOT NULL,
  `device_type` VARCHAR(60) NOT NULL DEFAULT '',
  `issue` VARCHAR(180) NOT NULL,
  `symptoms` TEXT NOT NULL,
  `steps` TEXT NOT NULL,
  `safety_note` TEXT NOT NULL,
  `is_published` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  KEY `idx_guide_published_created` (`is_published`, `created_at`),
  FULLTEXT KEY `ftx_guide_search` (`title`, `issue`, `symptoms`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 10. Customer technical support tickets
-- Django: catalog.SupportTicket (user SET_NULL)
-- ============================================================================
CREATE TABLE IF NOT EXISTS `catalog_supportticket` (
  `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `user_id` BIGINT NULL,
  `name` VARCHAR(120) NOT NULL,
  `email` VARCHAR(254) NOT NULL,
  `subject` VARCHAR(180) NOT NULL,
  `description` TEXT NOT NULL,
  `status` VARCHAR(20) NOT NULL DEFAULT 'open',
  `priority` VARCHAR(20) NOT NULL DEFAULT 'normal',
  `staff_response` TEXT NOT NULL,
  `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  CONSTRAINT `chk_ticket_status`
    CHECK (`status` IN ('open','in_progress','resolved','closed')),
  CONSTRAINT `chk_ticket_priority`
    CHECK (`priority` IN ('low','normal','high')),
  CONSTRAINT `fk_ticket_user`
    FOREIGN KEY (`user_id`)
    REFERENCES `auth_user` (`id`)
    ON DELETE SET NULL
    ON UPDATE CASCADE,
  KEY `idx_ticket_user` (`user_id`),
  KEY `idx_ticket_status_priority` (`status`, `priority`),
  KEY `idx_ticket_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
