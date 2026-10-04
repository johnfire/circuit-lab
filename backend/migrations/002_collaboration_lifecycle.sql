-- Applied once under the application migration lock, not in the identity database.
CREATE TABLE IF NOT EXISTS collaboration_schema_versions (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS collaboration_accounts (
    owner text PRIMARY KEY,
    enabled boolean NOT NULL DEFAULT true,
    minimum_token_iat bigint NOT NULL DEFAULT 0
);
ALTER TABLE collaboration_actions ADD COLUMN IF NOT EXISTS outcome text NOT NULL DEFAULT 'success';
CREATE INDEX IF NOT EXISTS collaboration_runs_running ON collaboration_runs(document, status);
