"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createAdminCustomer,
  createAdminCustomerOperationalException,
  deactivateAdminCustomer,
  deleteAdminCustomerOperationalException,
  formatError,
  getAdminCustomerOperationalProfile,
  listAdminCustomers,
  listAdminCustomerOperationalExceptions,
  putAdminCustomerOperationalProfile,
  updateAdminCustomer,
  type Customer,
  type CustomerOperationalException,
  type CustomerOperationalExceptionType,
  type CustomerOperationalProfile,
  type Zone,
} from "../lib/api";

type AdminCustomersSectionProps = {
  token: string;
  zones: Zone[];
};

function shortId(value: string): string {
  return value.slice(0, 8);
}

export function AdminCustomersSection({ token, zones }: AdminCustomersSectionProps) {
  const [error, setError] = useState("");

  // List state
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerFilter, setCustomerFilter] = useState<"all" | "active" | "inactive">("all");
  const [customerZoneFilter, setCustomerZoneFilter] = useState("all");

  // Create form
  const [newCustomerName, setNewCustomerName] = useState("");
  const [newCustomerZoneId, setNewCustomerZoneId] = useState("");
  const [newCustomerPriority, setNewCustomerPriority] = useState("0");
  const [newCustomerCutoff, setNewCustomerCutoff] = useState("");

  // Edit form
  const [editingCustomerId, setEditingCustomerId] = useState("");
  const [editCustomerName, setEditCustomerName] = useState("");
  const [editCustomerZoneId, setEditCustomerZoneId] = useState("");
  const [editCustomerPriority, setEditCustomerPriority] = useState("0");
  const [editCustomerCutoff, setEditCustomerCutoff] = useState("");

  // Operational profile
  const [operationalProfile, setOperationalProfile] = useState<CustomerOperationalProfile | null>(null);
  const [operationalProfileLoading, setOperationalProfileLoading] = useState(false);
  const [operationalProfileSaving, setOperationalProfileSaving] = useState(false);
  const [opAcceptOrders, setOpAcceptOrders] = useState(true);
  const [opWindowStart, setOpWindowStart] = useState("");
  const [opWindowEnd, setOpWindowEnd] = useState("");
  const [opMinLeadHours, setOpMinLeadHours] = useState("0");
  const [opConsolidateByDefault, setOpConsolidateByDefault] = useState(false);
  const [opOpsNote, setOpOpsNote] = useState("");

  // Operational exceptions
  const [operationalExceptions, setOperationalExceptions] = useState<CustomerOperationalException[]>([]);
  const [operationalExceptionsLoading, setOperationalExceptionsLoading] = useState(false);
  const [operationalExceptionCreating, setOperationalExceptionCreating] = useState(false);
  const [operationalExceptionDeletingId, setOperationalExceptionDeletingId] = useState<string | null>(null);
  const [opExceptionDate, setOpExceptionDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [opExceptionType, setOpExceptionType] = useState<CustomerOperationalExceptionType>("blocked");
  const [opExceptionNote, setOpExceptionNote] = useState("");

  const refreshCustomers = useCallback(async () => {
    if (!token) return;
    setError("");
    try {
      const active = customerFilter === "all" ? undefined : customerFilter === "active";
      const zone_id = customerZoneFilter === "all" ? undefined : customerZoneFilter;
      const res = await listAdminCustomers(token, { active, zone_id });
      setCustomers(res.items ?? []);
    } catch (e) {
      setError(formatError(e));
    }
  }, [token, customerFilter, customerZoneFilter]);

  useEffect(() => {
    void refreshCustomers();
  }, [refreshCustomers]);

  const fillOperationalProfileForm = useCallback((profile: CustomerOperationalProfile) => {
    setOperationalProfile(profile);
    setOpAcceptOrders(profile.accept_orders);
    setOpWindowStart(profile.window_start ?? "");
    setOpWindowEnd(profile.window_end ?? "");
    setOpMinLeadHours(String(profile.min_lead_hours));
    setOpConsolidateByDefault(profile.consolidate_by_default);
    setOpOpsNote(profile.ops_note ?? "");
  }, []);

  const resetOperationalProfileForm = useCallback(() => {
    setOperationalProfile(null);
    setOpAcceptOrders(true);
    setOpWindowStart("");
    setOpWindowEnd("");
    setOpMinLeadHours("0");
    setOpConsolidateByDefault(false);
    setOpOpsNote("");
  }, []);

  const resetOperationalExceptionsState = useCallback(() => {
    setOperationalExceptions([]);
    setOperationalExceptionsLoading(false);
    setOperationalExceptionCreating(false);
    setOperationalExceptionDeletingId(null);
    setOpExceptionDate(new Date().toISOString().slice(0, 10));
    setOpExceptionType("blocked");
    setOpExceptionNote("");
  }, []);

  const loadCustomerOperationalProfile = useCallback(
    async (customerId: string) => {
      if (!token || !customerId) return;
      setOperationalProfileLoading(true);
      try {
        const profile = await getAdminCustomerOperationalProfile(token, customerId);
        fillOperationalProfileForm(profile);
      } catch (e) {
        setError(formatError(e));
      } finally {
        setOperationalProfileLoading(false);
      }
    },
    [token, fillOperationalProfileForm],
  );

  const loadCustomerOperationalExceptions = useCallback(
    async (customerId: string) => {
      if (!token || !customerId) return;
      setOperationalExceptionsLoading(true);
      try {
        const data = await listAdminCustomerOperationalExceptions(token, customerId);
        setOperationalExceptions(data.items ?? []);
      } catch (e) {
        setError(formatError(e));
      } finally {
        setOperationalExceptionsLoading(false);
      }
    },
    [token],
  );

  async function onCreateCustomer() {
    if (!token) return;
    if (!newCustomerName.trim()) {
      setError("El nombre de cliente es obligatorio");
      return;
    }
    if (!newCustomerZoneId) {
      setError("Debes seleccionar una zona");
      return;
    }
    try {
      await createAdminCustomer(token, {
        zone_id: newCustomerZoneId,
        name: newCustomerName.trim(),
        priority: Number.parseInt(newCustomerPriority, 10) || 0,
        cutoff_override_time: newCustomerCutoff.trim() || null,
      });
      setNewCustomerName("");
      setNewCustomerPriority("0");
      setNewCustomerCutoff("");
      await refreshCustomers();
    } catch (e) {
      setError(formatError(e));
    }
  }

  function startEditCustomer(customer: Customer) {
    setEditingCustomerId(customer.id);
    setEditCustomerName(customer.name);
    setEditCustomerZoneId(customer.zone_id);
    setEditCustomerPriority(String(customer.priority));
    setEditCustomerCutoff(customer.cutoff_override_time ?? "");
    void loadCustomerOperationalProfile(customer.id);
    void loadCustomerOperationalExceptions(customer.id);
  }

  function cancelEditCustomer() {
    setEditingCustomerId("");
    resetOperationalProfileForm();
    resetOperationalExceptionsState();
  }

  async function onSaveCustomerEdit() {
    if (!token || !editingCustomerId) return;
    if (!editCustomerName.trim()) {
      setError("El nombre de cliente es obligatorio");
      return;
    }
    if (!editCustomerZoneId) {
      setError("Debes seleccionar una zona");
      return;
    }
    try {
      await updateAdminCustomer(token, editingCustomerId, {
        zone_id: editCustomerZoneId,
        name: editCustomerName.trim(),
        priority: Number.parseInt(editCustomerPriority, 10) || 0,
        cutoff_override_time: editCustomerCutoff.trim() || null,
      });
      await loadCustomerOperationalProfile(editingCustomerId);
      await loadCustomerOperationalExceptions(editingCustomerId);
      await refreshCustomers();
    } catch (e) {
      setError(formatError(e));
    }
  }

  async function onDeactivateCustomer(customerId: string) {
    if (!token) return;
    const confirmed = window.confirm("¿Desactivar este cliente?");
    if (!confirmed) return;
    try {
      await deactivateAdminCustomer(token, customerId);
      if (editingCustomerId === customerId) {
        setEditingCustomerId("");
        resetOperationalProfileForm();
        resetOperationalExceptionsState();
      }
      await refreshCustomers();
    } catch (e) {
      setError(formatError(e));
    }
  }

  async function onSaveOperationalProfile() {
    if (!token || !editingCustomerId) return;
    const parsedMinLead = Number.parseInt(opMinLeadHours, 10);
    if (Number.isNaN(parsedMinLead)) {
      setError("min_lead_hours debe ser un entero");
      return;
    }
    setOperationalProfileSaving(true);
    try {
      const updated = await putAdminCustomerOperationalProfile(token, editingCustomerId, {
        accept_orders: opAcceptOrders,
        window_start: opWindowStart.trim() || null,
        window_end: opWindowEnd.trim() || null,
        min_lead_hours: parsedMinLead,
        consolidate_by_default: opConsolidateByDefault,
        ops_note: opOpsNote.trim() || null,
      });
      fillOperationalProfileForm(updated);
    } catch (e) {
      setError(formatError(e));
    } finally {
      setOperationalProfileSaving(false);
    }
  }

  async function onCreateOperationalException() {
    if (!token || !editingCustomerId) return;
    if (!opExceptionDate.trim()) {
      setError("date es obligatoria");
      return;
    }
    if (!opExceptionNote.trim()) {
      setError("note es obligatoria");
      return;
    }
    setOperationalExceptionCreating(true);
    try {
      await createAdminCustomerOperationalException(token, editingCustomerId, {
        date: opExceptionDate,
        type: opExceptionType,
        note: opExceptionNote.trim(),
      });
      setOpExceptionNote("");
      await loadCustomerOperationalExceptions(editingCustomerId);
    } catch (e) {
      setError(formatError(e));
    } finally {
      setOperationalExceptionCreating(false);
    }
  }

  async function onDeleteOperationalException(exceptionId: string) {
    if (!token || !editingCustomerId) return;
    const confirmed = window.confirm("¿Eliminar esta excepción operativa?");
    if (!confirmed) return;
    setOperationalExceptionDeletingId(exceptionId);
    try {
      await deleteAdminCustomerOperationalException(token, editingCustomerId, exceptionId);
      await loadCustomerOperationalExceptions(editingCustomerId);
    } catch (e) {
      setError(formatError(e));
    } finally {
      setOperationalExceptionDeletingId(null);
    }
  }

  return (
    <div className="admin-layout">
      {error && (
        <div className="card" style={{ gridColumn: "1 / -1", background: "#fef2f2", borderColor: "#fca5a5" }}>
          <p style={{ margin: 0, color: "#dc2626" }}>{error}</p>
        </div>
      )}

      <div className="card">
        <div className="row" style={{ marginBottom: 10 }}>
          <h2 style={{ marginRight: 12 }}>Listado de Clientes</h2>
          <select
            value={customerFilter}
            onChange={(e) => setCustomerFilter(e.target.value as "all" | "active" | "inactive")}
          >
            <option value="all">Todos</option>
            <option value="active">Activos</option>
            <option value="inactive">Inactivos</option>
          </select>
          <select value={customerZoneFilter} onChange={(e) => setCustomerZoneFilter(e.target.value)}>
            <option value="all">Todas las zonas</option>
            {zones.map((zone) => (
              <option key={zone.id} value={zone.id}>
                {zone.name}
              </option>
            ))}
          </select>
          <button className="secondary" onClick={() => void refreshCustomers()}>
            Refrescar
          </button>
        </div>
        <table>
          <thead>
            <tr>
              <th>id</th>
              <th>nombre</th>
              <th>zona</th>
              <th>prioridad</th>
              <th>cutoff override</th>
              <th>estado</th>
              <th>acciones</th>
            </tr>
          </thead>
          <tbody>
            {customers.length === 0 && (
              <tr>
                <td colSpan={7} style={{ color: "#6b7280" }}>
                  Sin clientes.
                </td>
              </tr>
            )}
            {customers.map((customer) => {
              const zoneName = zones.find((zone) => zone.id === customer.zone_id)?.name ?? shortId(customer.zone_id);
              return (
                <tr key={customer.id}>
                  <td>{shortId(customer.id)}</td>
                  <td>{customer.name}</td>
                  <td>{zoneName}</td>
                  <td>{customer.priority}</td>
                  <td>{customer.cutoff_override_time ?? "-"}</td>
                  <td>
                    <span className={customer.active ? "badge ok" : "badge rejected"}>
                      {customer.active ? "active" : "inactive"}
                    </span>
                  </td>
                  <td className="row">
                    <button className="secondary" onClick={() => startEditCustomer(customer)}>
                      Editar
                    </button>
                    {customer.active && (
                      <button className="danger" onClick={() => onDeactivateCustomer(customer.id)}>
                        Desactivar
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="grid" style={{ gap: 12 }}>
        <div className="card grid">
          <h2>Crear Cliente</h2>
          <input
            placeholder="Nombre cliente"
            value={newCustomerName}
            onChange={(e) => setNewCustomerName(e.target.value)}
          />
          <select value={newCustomerZoneId} onChange={(e) => setNewCustomerZoneId(e.target.value)}>
            <option value="">Selecciona zona</option>
            {zones.map((zone) => (
              <option key={zone.id} value={zone.id}>
                {zone.name}
              </option>
            ))}
          </select>
          <input
            placeholder="Prioridad (int)"
            value={newCustomerPriority}
            onChange={(e) => setNewCustomerPriority(e.target.value)}
          />
          <input
            placeholder="cutoff_override_time HH:MM:SS (opcional)"
            value={newCustomerCutoff}
            onChange={(e) => setNewCustomerCutoff(e.target.value)}
          />
          <button onClick={() => void onCreateCustomer()}>Crear</button>
        </div>

        <div className="card grid">
          <h2>Editar Cliente</h2>
          {!editingCustomerId && <p style={{ margin: 0, color: "#6b7280" }}>Selecciona un cliente para editar.</p>}
          {editingCustomerId && (
            <>
              <input value={editCustomerName} onChange={(e) => setEditCustomerName(e.target.value)} />
              <select value={editCustomerZoneId} onChange={(e) => setEditCustomerZoneId(e.target.value)}>
                <option value="">Selecciona zona</option>
                {zones.map((zone) => (
                  <option key={zone.id} value={zone.id}>
                    {zone.name}
                  </option>
                ))}
              </select>
              <input value={editCustomerPriority} onChange={(e) => setEditCustomerPriority(e.target.value)} />
              <input value={editCustomerCutoff} onChange={(e) => setEditCustomerCutoff(e.target.value)} />
              <div className="row">
                <button onClick={() => void onSaveCustomerEdit()}>Guardar</button>
                <button className="secondary" onClick={cancelEditCustomer}>
                  Cancelar
                </button>
              </div>
            </>
          )}
        </div>

        <div className="card grid">
          <h2>Perfil Operativo</h2>
          {!editingCustomerId && (
            <p style={{ margin: 0, color: "#6b7280" }}>
              Selecciona un cliente (Editar) para ver y actualizar su perfil operativo.
            </p>
          )}
          {editingCustomerId && (
            <>
              {operationalProfileLoading && <p style={{ margin: 0, color: "#6b7280" }}>Cargando perfil...</p>}
              {operationalProfile && (
                <div className="row" style={{ gap: 6 }}>
                  <span className="pill">window_mode: {operationalProfile.window_mode}</span>
                  <span className="pill">tz: {operationalProfile.evaluation_timezone}</span>
                  <span className="pill">customized: {operationalProfile.is_customized ? "true" : "false"}</span>
                </div>
              )}
              <label className="row" style={{ gap: 6 }}>
                <input
                  type="checkbox"
                  checked={opAcceptOrders}
                  onChange={(e) => setOpAcceptOrders(e.target.checked)}
                />
                accept_orders
              </label>
              <input
                placeholder="window_start HH:MM:SS (opcional)"
                value={opWindowStart}
                onChange={(e) => setOpWindowStart(e.target.value)}
              />
              <input
                placeholder="window_end HH:MM:SS (opcional)"
                value={opWindowEnd}
                onChange={(e) => setOpWindowEnd(e.target.value)}
              />
              <input
                placeholder="min_lead_hours (entero >= 0)"
                value={opMinLeadHours}
                onChange={(e) => setOpMinLeadHours(e.target.value)}
              />
              <label className="row" style={{ gap: 6 }}>
                <input
                  type="checkbox"
                  checked={opConsolidateByDefault}
                  onChange={(e) => setOpConsolidateByDefault(e.target.checked)}
                />
                consolidate_by_default
              </label>
              <textarea
                placeholder="ops_note (opcional)"
                value={opOpsNote}
                onChange={(e) => setOpOpsNote(e.target.value)}
                rows={4}
              />
              <div className="row">
                <button onClick={() => void onSaveOperationalProfile()} disabled={operationalProfileSaving}>
                  {operationalProfileSaving ? "Guardando..." : "Guardar perfil"}
                </button>
                <button
                  className="secondary"
                  onClick={() => {
                    void loadCustomerOperationalProfile(editingCustomerId);
                  }}
                  disabled={operationalProfileLoading || operationalProfileSaving}
                >
                  Recargar perfil
                </button>
              </div>
            </>
          )}
        </div>

        <div className="card grid">
          <h2>Excepciones Operativas</h2>
          {!editingCustomerId && (
            <p style={{ margin: 0, color: "#6b7280" }}>
              Selecciona un cliente (Editar) para gestionar excepciones por fecha.
            </p>
          )}
          {editingCustomerId && (
            <>
              <div className="row">
                <input type="date" value={opExceptionDate} onChange={(e) => setOpExceptionDate(e.target.value)} />
                <select
                  value={opExceptionType}
                  onChange={(e) => setOpExceptionType(e.target.value as CustomerOperationalExceptionType)}
                >
                  <option value="blocked">blocked</option>
                  <option value="restricted">restricted</option>
                </select>
              </div>
              <input
                placeholder="note (obligatoria)"
                value={opExceptionNote}
                onChange={(e) => setOpExceptionNote(e.target.value)}
              />
              <div className="row">
                <button onClick={() => void onCreateOperationalException()} disabled={operationalExceptionCreating}>
                  {operationalExceptionCreating ? "Creando..." : "Crear excepción"}
                </button>
                <button
                  className="secondary"
                  onClick={() => {
                    void loadCustomerOperationalExceptions(editingCustomerId);
                  }}
                  disabled={operationalExceptionsLoading || operationalExceptionCreating}
                >
                  Recargar excepciones
                </button>
              </div>
              {operationalExceptionsLoading && (
                <p style={{ margin: 0, color: "#6b7280" }}>Cargando excepciones...</p>
              )}
              <table>
                <thead>
                  <tr>
                    <th>date</th>
                    <th>type</th>
                    <th>note</th>
                    <th>created_at</th>
                    <th>acción</th>
                  </tr>
                </thead>
                <tbody>
                  {operationalExceptions.length === 0 && (
                    <tr>
                      <td colSpan={5} style={{ color: "#6b7280" }}>
                        Sin excepciones operativas para este cliente.
                      </td>
                    </tr>
                  )}
                  {operationalExceptions.map((item) => (
                    <tr key={item.id}>
                      <td>{item.date}</td>
                      <td>{item.type}</td>
                      <td>{item.note}</td>
                      <td>{new Date(item.created_at).toLocaleString("es-ES")}</td>
                      <td>
                        <button
                          className="danger"
                          onClick={() => {
                            void onDeleteOperationalException(item.id);
                          }}
                          disabled={operationalExceptionDeletingId === item.id}
                        >
                          {operationalExceptionDeletingId === item.id ? "Eliminando..." : "Eliminar"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
