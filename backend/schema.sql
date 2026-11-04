CREATE DATABASE IF NOT EXISTS master CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE master;

CREATE TABLE IF NOT EXISTS users_master (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  tenant_id VARCHAR(100) NOT NULL,
  role ENUM('admin', 'analyst', 'viewer') NOT NULL DEFAULT 'viewer',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_users_tenant (tenant_id)
);

CREATE TABLE IF NOT EXISTS db_connection (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  tenant_id VARCHAR(100) NOT NULL UNIQUE,
  shop_domain VARCHAR(255) NOT NULL UNIQUE,
  shopify_access_token_enc TEXT NOT NULL,
  connected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_connection_tenant (tenant_id)
);
