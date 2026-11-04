USE master;
ALTER TABLE db_connection
  ADD COLUMN shopify_refresh_token_enc TEXT NULL,
  ADD COLUMN access_token_expires_at DATETIME NULL,
  ADD COLUMN refresh_token_expires_at DATETIME NULL,
  ADD COLUMN scopes VARCHAR(1000) NOT NULL DEFAULT '';

ALTER TABLE users_master
  ADD COLUMN token_version INT UNSIGNED NOT NULL DEFAULT 0;
