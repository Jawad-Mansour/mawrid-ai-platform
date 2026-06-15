import { Routes, Route, Navigate } from "react-router-dom";
import { useBootstrapAuth } from "@/hooks/useAuth";
import { AppLayout } from "@/components/layout/AppLayout";
import { ChooseMode } from "@/pages/auth/ChooseMode";
import { Signup } from "@/pages/auth/Signup";
import { Login } from "@/pages/auth/Login";
import { Dashboard } from "@/pages/Dashboard";
import { Catalog } from "@/pages/Catalog";
import { Approvals } from "@/pages/Approvals";
import { Procurement } from "@/pages/Procurement";
import { Publishing } from "@/pages/Publishing";
import { Dunning } from "@/pages/Dunning";
import { Barcode } from "@/pages/Barcode";
import { AiHealth } from "@/pages/AiHealth";
import { Settings } from "@/pages/Settings";

export default function App() {
  useBootstrapAuth();
  return (
    <Routes>
      <Route path="/choose-mode" element={<ChooseMode />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/login" element={<Login />} />

      <Route element={<AppLayout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/catalog" element={<Catalog />} />
        <Route path="/approvals" element={<Approvals />} />
        <Route path="/procurement" element={<Procurement />} />
        <Route path="/publishing" element={<Publishing />} />
        <Route path="/dunning" element={<Dunning />} />
        <Route path="/barcode" element={<Barcode />} />
        <Route path="/ai-health" element={<AiHealth />} />
        <Route path="/settings" element={<Settings />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
