USE master;
CREATE TABLE IF NOT EXISTS store_alert_states (
  tenant_id VARCHAR(100) NOT NULL,
  alert_id VARCHAR(64) NOT NULL,
  resolved_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (tenant_id, alert_id)
);
