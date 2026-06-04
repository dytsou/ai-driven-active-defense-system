import { NavLink } from "react-router-dom";

function linkClass({ isActive }) {
  return isActive ? "active" : "";
}

export default function TopNav({ isAuthenticated = false, isAdmin = false }) {
  return (
    <nav className="top-nav" aria-label="Primary">
      <NavLink to="/" className={linkClass} end>
        Login
      </NavLink>
      {isAuthenticated && (
        <NavLink to="/me" className={linkClass}>
          My Profile
        </NavLink>
      )}
      {isAdmin && (
        <NavLink to="/admin/events" className={linkClass}>
          Admin Events
        </NavLink>
      )}
    </nav>
  );
}
