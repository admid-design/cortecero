import type { ReactNode } from "react";

export type AdminSection = "zones" | "customers" | "users" | "tenant" | "products";

export type AdminShellProps = {
  activeSection: AdminSection;
  onSectionChange: (section: AdminSection) => void;
  children: ReactNode;
};

export function AdminShell({ activeSection, onSectionChange, children }: AdminShellProps) {
  return (
    <section className="grid admin-shell">
      <div className="card admin-shell-header">
        <div>
          <h2>Panel de Administración</h2>
          <p style={{ margin: "4px 0 0", color: "#6b7280" }}>
            Gestión de Zonas, Clientes, Usuarios, Productos y Tenant.
          </p>
        </div>
      </div>
      <div className="admin-shell-layout">
        <aside className="card admin-sidebar">
          <nav className="grid" style={{ gap: "4px" }}>
            <button
              className={activeSection === "zones" ? "sidebar-item active" : "sidebar-item"}
              onClick={() => onSectionChange("zones")}
            >
              Zonas
            </button>
            <button
              className={activeSection === "customers" ? "sidebar-item active" : "sidebar-item"}
              onClick={() => onSectionChange("customers")}
            >
              Clientes
            </button>
            <button
              className={activeSection === "users" ? "sidebar-item active" : "sidebar-item"}
              onClick={() => onSectionChange("users")}
            >
              Usuarios
            </button>
            <button
              className={activeSection === "products" ? "sidebar-item active" : "sidebar-item"}
              onClick={() => onSectionChange("products")}
            >
              Productos
            </button>
            <button
              className={activeSection === "tenant" ? "sidebar-item active" : "sidebar-item"}
              onClick={() => onSectionChange("tenant")}
            >
              Tenant
            </button>
          </nav>
        </aside>
        <div className="admin-shell-content grid">
          {children}
        </div>
      </div>
    </section>
  );
}
