import { NavLink } from "react-router-dom";

function sidebarLinkClass({ isActive }) {
  return isActive ? "active" : "";
}

export default function DashboardLayout({
  username = "",
  role = "",
  isAdmin = false,
  breadcrumb = "個人資料",
  children,
}) {
  const roleLabel = role === "admin" ? "管理員" : "使用者";
  const userDisplay = username ? `${username} · ${roleLabel}` : roleLabel;

  return (
    <div className="dashboard-shell">
      <aside className="dashboard-sidebar">
        <div className="dashboard-sidebar-header">
          <img
            className="dashboard-sidebar-logo"
            src="https://portal.nycu.edu.tw/img/nycu-logo.png"
            alt=""
            aria-hidden="true"
          />
          <span>校園單一入口</span>
        </div>
        <ul className="dashboard-sidebar-menu">
          <li>
            <NavLink to="/me" className={sidebarLinkClass} end>
              <span className="dashboard-menu-icon" aria-hidden="true">
                🔗
              </span>
              校務系統連結
            </NavLink>
          </li>
          {isAdmin && (
            <li>
              <NavLink to="/admin/events" className={sidebarLinkClass}>
                <span className="dashboard-menu-icon" aria-hidden="true">
                  🛡️
                </span>
                威脅情報監控
              </NavLink>
            </li>
          )}
          <li>
            <span className="dashboard-sidebar-static">
              <span className="dashboard-menu-icon" aria-hidden="true">
                🌐
              </span>
              陽明交大首頁
            </span>
          </li>
          <li>
            <NavLink to="/" className={sidebarLinkClass}>
              <span className="dashboard-menu-icon" aria-hidden="true">
                🔑
              </span>
              返回登入
            </NavLink>
          </li>
        </ul>
      </aside>

      <div className="dashboard-main">
        <header className="dashboard-navbar">
          <div className="dashboard-breadcrumb">
            <img
              className="dashboard-navbar-logo"
              src="https://portal.nycu.edu.tw/img/nycu-logo.png"
              alt=""
              aria-hidden="true"
            />
            ☰ 校園單一入口 / <span>{breadcrumb}</span>
          </div>
          <div className="dashboard-user">{userDisplay} ▾</div>
        </header>
        <main className="dashboard-content">{children}</main>
      </div>
    </div>
  );
}
