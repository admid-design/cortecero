-- Migration 020: stop_proofs
-- Prueba de entrega: firma digital del receptor vinculada a una parada.
-- Bloque A2 (POD-001)

CREATE TABLE IF NOT EXISTS stop_proofs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  route_stop_id UUID NOT NULL,
  route_id UUID NOT NULL,
  proof_type TEXT NOT NULL CHECK (proof_type IN ('signature', 'photo', 'both')),
  -- Firma como base64 PNG (< 50 KB recomendado)
  signature_data TEXT,
  -- URL futura a object storage (fase D)
  photo_url TEXT,
  -- Nombre del receptor (opcional)
  signed_by TEXT,
  captured_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_stop_proofs_stop ON stop_proofs(route_stop_id);
CREATE INDEX IF NOT EXISTS idx_stop_proofs_route ON stop_proofs(route_id);
CREATE INDEX IF NOT EXISTS idx_stop_proofs_tenant ON stop_proofs(tenant_id);
