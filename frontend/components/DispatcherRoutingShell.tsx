import type { ReactNode } from "react";

type DispatcherRoutingShellProps = {
  serviceDate: string;
  onServiceDateChange: (value: string) => void;
  onRefresh: () => void;
  loading: boolean;
  routeCount: number;
  readyOrderCount: number;
  vehicleCount: number;
  children: ReactNode;
};

export function DispatcherRoutingShell({
  serviceDate,
  onServiceDateChange,
  onRefresh,
  loading,
  routeCount,
  readyOrderCount,
  vehicleCount,
  children,
}: DispatcherRoutingShellProps) {
  return (
    <section className="grid dispatcher-routing-shell">
      <div className="card dispatcher-routing-shell-header">
        <div>
          <h2>Routing Dispatcher</h2>
          <p style={{ margin: "4px 0 0", color: "var(--muted)" }}>
            Planificación, optimización y despacho sobre la fecha operativa activa.
          </p>
        </div>
        <div className="row">
          <span className="pill">rutas: {routeCount}</span>
          <span className="pill">ready orders: {readyOrderCount}</span>
          <span className="pill">vehículos: {vehicleCount}</span>
        </div>
      </div>
      <div className="card row dispatcher-routing-shell-actions">
        <input type="date" value={serviceDate} onChange={(e) => onServiceDateChange(e.target.value)} />
        <button className="secondary" onClick={onRefresh} disabled={loading}>
          {loading ? "Refrescando..." : "Refrescar operación"}
        </button>
      </div>
      {children}
    </section>
  );
}
