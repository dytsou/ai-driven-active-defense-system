import { Route, Routes } from "react-router-dom";
import AdminEventsPage from "./pages/AdminEventsPage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import MfaPage from "./pages/MfaPage.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LoginPage />} />
      <Route path="/mfa" element={<MfaPage />} />
      <Route path="/admin/events" element={<AdminEventsPage />} />
    </Routes>
  );
}
