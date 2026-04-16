import React, { useCallback, useEffect, useState } from "react";
import {
  createAdminZone,
  deactivateAdminZone,
  formatError,
  listAdminZones,
  updateAdminZone,
  type Zone,
} from "../lib/api";

type AdminZonesSectionProps = {
  token: string;
};

function shortId(value: string): string {
  return value.slice(0, 8);
}

export function AdminZonesSection({ token }: AdminZonesSectionProps) {
  const [error, setError] = useState("");
  const [zones, setZones] = useState<Zone[]>([]);
  const [zoneFilter, setZoneFilter] = useState<"all" | "active" | "inactive">("all");

  const [newZoneName, setNewZoneName] = useState("");
  const [newZoneCutoff, setNewZoneCutoff] = useState("10:00:00");
  const [newZoneTimezone, setNewZoneTimezone] = useState("Europe/Madrid");

  const [editingZoneId, setEditingZoneId] = useState("");
  const [editZoneName, setEditZoneName] = useState("");
  const [editZoneCutoff, setEditZoneCutoff] = useState("10:00:00");
  const [editZoneTimezone, setEditZoneTimezone] = useState("Europe/Madrid");

  const loadZones = useCallback(async () => {
    if (!token) return;
    setError("");
    try {
      const active = zoneFilter === "all" ? undefined : zoneFilter === "active";
      const res = await listAdminZones(token, { active });
      setZones(res.items ?? []);
    } catch (e) {
      setError(formatError(e));
    }
  }, [token, zoneFilter]);

  useEffect(() => {
    void loadZones();
  }, [loadZones]);

  async function onCreateZone() {
    if (!token) return;
    if (!newZoneName.trim()) {
      setError("El nombre de zona es obligatorio");
      return;
    }
    setError("");
    try {
      await createAdminZone(token, {
        name: newZoneName.trim(),
        default_cutoff_time: newZoneCutoff,
        timezone: newZoneTimezone.trim(),
      });
      setNewZoneName("");
      await loadZones();
    } catch (e) {
      setError(formatError(e));
    }
  }

  function startEditZone(zone: Zone) {
    setEditingZoneId(zone.id);
    setEditZoneName(zone.name);
    setEditZoneCutoff(zone.default_cutoff_time);
    setEditZoneTimezone(zone.timezone);
  }

  function cancelEditZone() {
    setEditingZoneId("");
  }

  async function onSaveZoneEdit() {
    if (!token || !editingZoneId) return;
    if (!editZoneName.trim()) {
      setError("El nombre de zona es obligatorio");
      return;
    }
    setError("");
    try {
      await updateAdminZone(token, editingZoneId, {
        name: editZoneName.trim(),
        default_cutoff_time: editZoneCutoff,
        timezone: editZoneTimezone.trim(),
      });
      setEditingZoneId("");
      await loadZones();
    } catch (e) {
      setError(formatError(e));
    }
  }

  async function onDeactivateZone(zoneId: string) {
    if (!token) return;
    const confirmed = window.confirm("¿Desactivar esta zona?");
    if (!confirmed) return;
    setError("");
    try {
      await deactivateAdminZone(token, zoneId);
      if (editingZoneId === zoneId) {
        setEditingZoneId("");
      }
      await loadZones();
    } catch (e) {
      setError(formatError(e));
    }
  }

  return (
    <div className="grid cols-2">
      {error && (
        <div className="card" style={{ gridColumn: "1 / -1", backgroundColor: "#fef2f2", borderColor: "#fca5a5" }}>
          <p style={{ margin: 0, color: "#b91c1c", fontWeight: "bold" }}>{error}</p>
        </div>
      )}

      <div className="card grid">
        <h2>Crear Zona</h2>
        <input placeholder="Nombre" value={newZoneName} onChange={(e) => setNewZoneName(e.target.value)} />
        <input
          placeholder="default_cutoff_time HH:MM:SS"
          value={newZoneCutoff}
          onChange={(e) => setNewZoneCutoff(e.target.value)}
        />
        <input
          placeholder="Timezone IANA"
          value={newZoneTimezone}
          onChange={(e) => setNewZoneTimezone(e.target.value)}
        />
        <button onClick={() => void onCreateZone()}>Crear</button>
      </div>

      <div className="card grid">
        <h2>Editar Zona</h2>
        {!editingZoneId && <p style={{ margin: 0, color: "#6b7280" }}>Selecciona una zona para editar.</p>}
        {editingZoneId && (
          <>
            <input value={editZoneName} onChange={(e) => setEditZoneName(e.target.value)} />
            <input value={editZoneCutoff} onChange={(e) => setEditZoneCutoff(e.target.value)} />
            <input value={editZoneTimezone} onChange={(e) => setEditZoneTimezone(e.target.value)} />
            <div className="row">
              <button onClick={() => void onSaveZoneEdit()}>Guardar</button>
              <button className="secondary" onClick={cancelEditZone}>
                Cancelar
              </button>
            </div>
          </>
        )}
      </div>

      <div className="card" style={{ gridColumn: "1 / -1" }}>
        <div className="row" style={{ marginBottom: 10 }}>
          <h2 style={{ marginRight: 12 }}>Listado de Zonas</h2>
          <select
            value={zoneFilter}
            onChange={(e) => setZoneFilter(e.target.value as "all" | "active" | "inactive")}
          >
            <option value="all">Todas</option>
            <option value="active">Activas</option>
            <option value="inactive">Inactivas</option>
          </select>
          <button className="secondary" onClick={() => void loadZones()}>
            Refrescar
          </button>
        </div>
        <table>
          <thead>
            <tr>
              <th>id</th>
              <th>nombre</th>
              <th>cutoff</th>
              <th>timezone</th>
              <th>estado</th>
              <th>acciones</th>
            </tr>
          </thead>
          <tbody>
            {zones.length === 0 && (
              <tr>
                <td colSpan={6} style={{ color: "#6b7280", textAlign: "center" }}>
                  Sin zonas encontradas.
                </td>
              </tr>
            )}
            {zones.map((zone) => (
              <tr key={zone.id}>
                <td>{shortId(zone.id)}</td>
                <td>{zone.name}</td>
                <td>{zone.default_cutoff_time}</td>
                <td>{zone.timezone}</td>
                <td>
                  <span className={zone.active ? "badge ok" : "badge rejected"}>
                    {zone.active ? "active" : "inactive"}
                  </span>
                </td>
                <td className="row">
                  <button className="secondary" onClick={() => startEditZone(zone)}>
                    Editar
                  </button>
                  {zone.active && (
                    <button className="danger" onClick={() => void onDeactivateZone(zone.id)}>
                      Desactivar
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
