import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AudioLines,
  LayoutDashboard,
  ScanLine,
  Library,
  Database,
  History,
  Settings2,
  ArrowUpRight,
  Menu,
  X,
  Circle,
} from "lucide-react";
import { api } from "../../api/client";
import { brand } from "../../config/brand";
import { archiveMode } from "../../config/hosting";
const links = [
  { to: "/dashboard", name: "Overview", icon: LayoutDashboard },
  { to: "/analyze", name: "Analyze speech", icon: ScanLine },
  { to: "/references", name: "Reference library", icon: Library },
  { to: "/datasets", name: "Contrastive dataset", icon: Database },
  { to: "/history", name: "Analysis history", icon: History },
  { to: "/settings", name: "Settings & rubrics", icon: Settings2 },
];
export default function AppLayout() {
  const [menu, setMenu] = useState(false);
  const provider = useQuery({ queryKey: ["provider"], queryFn: api.provider });
  return (
    <div className="app-shell">
      <aside className={`sidebar ${menu ? "open" : ""}`}>
        <Link className="brand" to="/">
          <span className="brand-icon">
            <AudioLines size={23} />
          </span>
          <span>
            {brand.name}
            <small>{brand.tagline}</small>
          </span>
        </Link>
        <p className="nav-label">WORKSPACE</p>
        <nav id="workspace-navigation">
          {links.map(({ to, name, icon: Icon }) => (
            <NavLink key={to} to={to} onClick={() => setMenu(false)}>
              <Icon size={18} />
              {name}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="engine-card">
            <span className="row">
              <Circle
                size={8}
                fill={provider.data?.ready ? "#7bcfa4" : "#e7b26a"}
              />
              <strong>
                {archiveMode ? "Saved real results" : provider.data?.ready
                  ? "Provider ready"
                  : "Provider unavailable"}
              </strong>
            </span>
            <p>
              {provider.data?.execution_mode === "mock"
                ? "Demo fixtures · no models loaded"
                : provider.data?.message || "Connecting to backend…"}
            </p>
            <Link to="/settings">
              View configuration <ArrowUpRight size={13} />
            </Link>
          </div>
          <p className="muted tiny">
            Single-user development workspace
            <br />
            Track C · Multimodal AI Hackathon
          </p>
        </div>
      </aside>
      <div className="app-main">
        <header className="topbar">
          <button
            className="mobile-menu"
            aria-label="Toggle navigation"
            aria-expanded={menu}
            aria-controls="workspace-navigation"
            onClick={() => setMenu(!menu)}
          >
            {menu ? <X /> : <Menu />}
          </button>
          <span className="muted">
            Workspace <span className="separator">/</span> Speech analytics
          </span>
          <div className="row">
            <span className="badge">
              {archiveMode ? "REPORT VIEWER" : provider.data?.execution_mode === "mock"
                ? "DEMO MODE"
                : provider.data?.ready
                  ? "MODEL CONNECTED"
                  : "OFFLINE"}
            </span>
            <span className="avatar">V</span>
          </div>
        </header>
        <main className="content">
          {archiveMode && <div className="notice">Hosted report viewer · saved real model results. Playback, charts, spoken feedback and downloads work without the project laptop. New analysis and editing require the full workspace.</div>}
          {import.meta.env.VITE_PUBLIC_DEMO === "true" && <div className="notice">Temporary public demo · use public/test audio only. Baselines and example reports are protected; new items belong to this browser session. CPU processing may take a minute.</div>}
          <Outlet />
        </main>
        <footer className="app-footer">
          {brand.name} {brand.version}
          <span>Evidence. Context. Better delivery.</span>
        </footer>
      </div>
    </div>
  );
}
