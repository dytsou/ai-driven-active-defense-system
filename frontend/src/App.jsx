import { Route, Routes } from "react-router-dom";
import AdminEventsPage from "./pages/AdminEventsPage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import MePage from "./pages/MePage.jsx";
import MfaPage from "./pages/MfaPage.jsx";
import RegisterPage from "./pages/RegisterPage.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LoginPage />} />
      <Route path="/me" element={<MePage />} />
      <Route path="/mfa" element={<MfaPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/admin/events" element={<AdminEventsPage />} />
    </Routes>
  );
}
