-- EduMeet 业务库 MySQL 8 schema. 可重复执行，不会删除或清空已有数据。
-- 本脚本只管理 EduMeet 业务数据，不创建、不迁移、不修改任何 Langfuse 表。
-- Langfuse 观测数据继续由 LANGFUSE_HOST 指向的现有 Langfuse 服务独立存储。
CREATE DATABASE IF NOT EXISTS `edumeet`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE `edumeet`;

CREATE TABLE IF NOT EXISTS `users` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(64) NOT NULL,
  `nickname` VARCHAR(64) NOT NULL DEFAULT '',
  `password_hash` VARCHAR(256) NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_users_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `llm_models` (
  `id` VARCHAR(64) NOT NULL,
  `name` VARCHAR(64) NOT NULL,
  `vendor` VARCHAR(64) NOT NULL,
  `free` TINYINT(1) NOT NULL DEFAULT 0,
  `description` VARCHAR(256) NOT NULL DEFAULT '',
  `provider` VARCHAR(32) NOT NULL DEFAULT 'mock',
  `enabled` TINYINT(1) NOT NULL DEFAULT 1,
  `sort_order` INT NOT NULL DEFAULT 100,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_llm_models_enabled` (`enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `sessions` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `title` VARCHAR(128) NOT NULL DEFAULT '新会话',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_sessions_user_id` (`user_id`),
  CONSTRAINT `fk_sessions_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `messages` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `session_id` INT NOT NULL,
  `role` VARCHAR(16) NOT NULL,
  `content` TEXT NOT NULL,
  `citations` JSON NULL,
  `model_id` VARCHAR(64) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_messages_session_id` (`session_id`),
  CONSTRAINT `fk_messages_session_id` FOREIGN KEY (`session_id`) REFERENCES `sessions` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `articles` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `author_id` INT NOT NULL,
  `title` VARCHAR(200) NOT NULL,
  `status` VARCHAR(16) NOT NULL DEFAULT 'draft',
  `source` VARCHAR(16) NOT NULL DEFAULT 'ai_generated',
  `content_md` TEXT NOT NULL,
  `model_id` VARCHAR(64) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `published_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  KEY `ix_articles_author_id` (`author_id`),
  KEY `ix_articles_author_status` (`author_id`, `status`),
  CONSTRAINT `fk_articles_author_id` FOREIGN KEY (`author_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `generation_tasks` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `topic` VARCHAR(200) NOT NULL,
  `status` VARCHAR(16) NOT NULL DEFAULT 'succeeded',
  `article_id` INT NULL,
  `model_id` VARCHAR(64) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_generation_tasks_user_id` (`user_id`),
  KEY `ix_generation_tasks_article_id` (`article_id`),
  CONSTRAINT `fk_generation_tasks_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `fk_generation_tasks_article_id` FOREIGN KEY (`article_id`) REFERENCES `articles` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `llm_models`
  (`id`, `name`, `vendor`, `free`, `description`, `provider`, `enabled`, `sort_order`)
VALUES
  ('doubao-lite', '豆包 Lite', '字节火山', 1, '免费模型（每日额度内），沙箱用户唯一可用', 'mock', 1, 1),
  ('doubao-pro', '豆包 Pro', '字节火山', 0, 'P0 文本主力，教育内容质量佳', 'mock', 1, 2),
  ('deepseek-chat', 'DeepSeek V3', 'DeepSeek', 0, 'P0 文本，真实接入已启用', 'deepseek', 1, 3),
  ('qwen3', '通义千问 Qwen3', '阿里', 0, 'P0 文本，中文政策语料友好', 'mock', 1, 4) AS new
ON DUPLICATE KEY UPDATE
  `name` = new.`name`,
  `vendor` = new.`vendor`,
  `free` = new.`free`,
  `description` = new.`description`,
  `sort_order` = new.`sort_order`;
