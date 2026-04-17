-- Migration 026: mensajes de chat por ruta
-- B3 — CHAT-001: canal de comunicación interno dispatcher ↔ conductor
-- Tabla append-only: no se permite UPDATE ni DELETE a nivel aplicación.

CREATE TABLE IF NOT EXISTS route_messages (
    id              UUID        NOT NULL DEFAULT gen_random_uuid(),
    tenant_id       UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    route_id        UUID        NOT NULL,
    author_user_id  UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    author_role     TEXT        NOT NULL,   -- 'dispatcher' | 'driver'
    body            TEXT        NOT NULL CHECK (char_length(body) BETWEEN 1 AND 2000),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_route_messages PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_route_messages_route
    ON route_messages (tenant_id, route_id, created_at);

CREATE INDEX IF NOT EXISTS idx_route_messages_author
    ON route_messages (tenant_id, author_user_id);
