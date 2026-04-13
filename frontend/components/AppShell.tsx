import type { ReactNode } from "react";

type SidebarItem = {
  id: string;
  label: string;
  active?: boolean;
  onClick?: () => void;
};

type TopTabItem = {
  id: string;
  label: string;
  active?: boolean;
  onClick?: () => void;
};

type AppShellProps = {
  header: ReactNode;
  topTabs?: ReactNode;
  banner?: ReactNode;
  sidebar?: ReactNode;
  children: ReactNode;
};

export function AppShell({ header, topTabs, banner, sidebar, children }: AppShellProps) {
  return (
    <main className="ops-app">
      <div className="ops-shell">
        {sidebar}
        <section className="ops-content">
          {header}
          {topTabs}
          {banner}
          {children}
        </section>
      </div>
    </main>
  );
}

type SectionHeaderProps = {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
};

export function SectionHeader({ title, subtitle, actions }: SectionHeaderProps) {
  return (
    <header className="section-header card">
      <div>
        <h1>{title}</h1>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
      {actions ? <div className="section-header-actions">{actions}</div> : null}
    </header>
  );
}

type GlobalBannerProps = {
  tone?: "neutral" | "error";
  children: ReactNode;
};

export function GlobalBanner({ tone = "neutral", children }: GlobalBannerProps) {
  const toneClass = tone === "error" ? "global-banner error" : "global-banner";
  return <div className={toneClass}>{children}</div>;
}

type TopTabsProps = {
  items: TopTabItem[];
};

export function TopTabs({ items }: TopTabsProps) {
  return (
    <div className="top-tabs card row">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          className={item.active ? "tab active" : "tab"}
          onClick={item.onClick}
          disabled={!item.onClick}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

type SidebarNavProps = {
  title?: string;
  items: SidebarItem[];
};

export function SidebarNav({ title = "Navegación", items }: SidebarNavProps) {
  return (
    <aside className="sidebar-nav card">
      <h2>{title}</h2>
      <nav>
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className={item.active ? "sidebar-item active" : "sidebar-item"}
            onClick={item.onClick}
            disabled={!item.onClick}
          >
            {item.label}
          </button>
        ))}
      </nav>
    </aside>
  );
}
