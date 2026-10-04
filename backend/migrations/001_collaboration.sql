-- Application data only: never apply this schema to the Keycloak database.
CREATE TABLE IF NOT EXISTS collaboration_documents (
    id uuid PRIMARY KEY,
    owner text NOT NULL,
    name text NOT NULL CHECK (length(name) BETWEEN 1 AND 80),
    kind text NOT NULL CHECK (kind IN ('project', 'workspace')),
    head uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS collaboration_documents_owner ON collaboration_documents(owner);

CREATE TABLE IF NOT EXISTS collaboration_revisions (
    id uuid PRIMARY KEY,
    document uuid NOT NULL REFERENCES collaboration_documents(id) ON DELETE CASCADE,
    parent uuid,
    contents jsonb NOT NULL,
    contents_hash text NOT NULL,
    actor text NOT NULL,
    reason text NOT NULL CHECK (length(reason) BETWEEN 1 AND 240),
    correlation_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(document, id),
    FOREIGN KEY(document, parent) REFERENCES collaboration_revisions(document, id)
        DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS collaboration_revisions_document ON collaboration_revisions(document, created_at);

CREATE OR REPLACE FUNCTION refuse_collaboration_revision_update() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Collaboration revisions are immutable';
END;
$$ LANGUAGE plpgsql;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'collaboration_revisions_immutable') THEN
        CREATE TRIGGER collaboration_revisions_immutable BEFORE UPDATE ON collaboration_revisions
            FOR EACH ROW EXECUTE FUNCTION refuse_collaboration_revision_update();
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'collaboration_document_head') THEN
        ALTER TABLE collaboration_documents ADD CONSTRAINT collaboration_document_head
            FOREIGN KEY(id, head) REFERENCES collaboration_revisions(document, id)
            DEFERRABLE INITIALLY DEFERRED;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS collaboration_grants (
    id uuid PRIMARY KEY,
    document uuid NOT NULL REFERENCES collaboration_documents(id) ON DELETE CASCADE,
    owner text NOT NULL,
    client text NOT NULL,
    scopes text[] NOT NULL,
    mode text NOT NULL CHECK (mode IN ('oauth', 'token')),
    token_hash text UNIQUE,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(document, id)
);
CREATE INDEX IF NOT EXISTS collaboration_grants_owner_client ON collaboration_grants(owner, client);

CREATE TABLE IF NOT EXISTS collaboration_actions (
    id uuid PRIMARY KEY,
    owner_hash text NOT NULL,
    target uuid NOT NULL,
    actor text NOT NULL,
    action text NOT NULL,
    before_revision uuid,
    after_revision uuid,
    correlation_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS collaboration_actions_owner ON collaboration_actions(owner_hash, created_at);

CREATE OR REPLACE FUNCTION refuse_collaboration_audit_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Collaboration audit is append-only';
END;
$$ LANGUAGE plpgsql;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'collaboration_actions_immutable') THEN
        CREATE TRIGGER collaboration_actions_immutable BEFORE UPDATE OR DELETE ON collaboration_actions
            FOR EACH ROW EXECUTE FUNCTION refuse_collaboration_audit_mutation();
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS collaboration_retries (
    owner text NOT NULL,
    actor text NOT NULL,
    request_key uuid NOT NULL,
    request_hash text NOT NULL,
    response jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (owner, actor, request_key)
);

CREATE TABLE IF NOT EXISTS collaboration_runs (
    id uuid PRIMARY KEY,
    document uuid NOT NULL REFERENCES collaboration_documents(id) ON DELETE CASCADE,
    revision uuid NOT NULL,
    analysis text NOT NULL CHECK (analysis IN ('transient', 'ac')),
    settings jsonb NOT NULL,
    status text NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'interrupted')),
    report jsonb,
    error text,
    actor text NOT NULL,
    correlation_id text NOT NULL,
    build_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY(document, revision) REFERENCES collaboration_revisions(document, id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS collaboration_runs_document ON collaboration_runs(document, created_at);

CREATE TABLE IF NOT EXISTS collaboration_view_commands (
    id uuid PRIMARY KEY,
    document uuid NOT NULL REFERENCES collaboration_documents(id) ON DELETE CASCADE,
    grant_id uuid NOT NULL,
    revision uuid NOT NULL,
    command jsonb NOT NULL,
    expires_at timestamptz NOT NULL DEFAULT now() + interval '30 seconds',
    acknowledged_at timestamptz,
    FOREIGN KEY(document, revision) REFERENCES collaboration_revisions(document, id) ON DELETE CASCADE,
    FOREIGN KEY(document, grant_id) REFERENCES collaboration_grants(document, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS collaboration_identity_events (
    event_id uuid PRIMARY KEY,
    subject_hash text NOT NULL,
    action text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
