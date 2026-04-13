import type { DashboardSummary } from "../lib/api";

type KpiRowProps = {
  summary: DashboardSummary;
};

type KpiItem = {
  key: string;
  label: string;
  value: number;
};

export function KpiRow({ summary }: KpiRowProps) {
  const items: KpiItem[] = [
    { key: "total", label: "Total pedidos", value: summary.total_orders },
    { key: "late", label: "Tardíos", value: summary.late_orders },
    { key: "open", label: "Planes open", value: summary.plans_open },
    { key: "locked", label: "Planes locked", value: summary.plans_locked },
    { key: "pending", label: "Excepciones pending", value: summary.pending_exceptions },
    { key: "approved", label: "Excepciones approved", value: summary.approved_exceptions },
  ];

  return (
    <section className="card grid kpi-row">
      <div className="kpi-row-header">
        <h2>KPIs operativos</h2>
      </div>
      <div className="metric-grid">
        {items.map((item) => (
          <div key={item.key}>
            <strong>{item.label}</strong>
            <p>{item.value}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
