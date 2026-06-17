import { Routes, Route, Navigate } from "react-router-dom";
import { useBootstrapAuth } from "@/hooks/useAuth";
import { useApplyTheme } from "@/stores/theme";
import { LogoutOverlay } from "@/components/LogoutOverlay";
import { Intelligence } from "@/pages/Intelligence";
import { Suppliers } from "@/pages/Suppliers";
import { AppLayout } from "@/components/layout/AppLayout";
import { ChooseMode } from "@/pages/auth/ChooseMode";
import { Signup } from "@/pages/auth/Signup";
import { Login } from "@/pages/auth/Login";
import { Dashboard } from "@/pages/Dashboard";
import { UploadPage } from "@/pages/UploadPage";
import { UploadHistory } from "@/pages/UploadHistory";
import { NeedsReview } from "@/pages/NeedsReview";
import { NotificationsPage } from "@/pages/NotificationsPage";
import { Profile } from "@/pages/Profile";
import { Catalog } from "@/pages/Catalog";
import { Approvals } from "@/pages/Approvals";
import { Procurement } from "@/pages/Procurement";
import { OrderReview } from "@/pages/OrderReview";
import { PurchaseOrders } from "@/pages/PurchaseOrders";
import { POThread } from "@/pages/POThread";
import { Publishing } from "@/pages/Publishing";
import { Dunning } from "@/pages/Dunning";
import { Barcode } from "@/pages/Barcode";
import { AiHealth } from "@/pages/AiHealth";
import { Settings } from "@/pages/Settings";

export default function App() {
  useBootstrapAuth();
  useApplyTheme();
  return (
    <>
    <LogoutOverlay />
    <Routes>
      <Route path="/choose-mode" element={<ChooseMode />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/login" element={<Login />} />

      <Route element={<AppLayout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/uploads" element={<UploadHistory />} />
        <Route path="/catalog" element={<Catalog />} />
        <Route path="/needs-review" element={<NeedsReview />} />
        <Route path="/approvals" element={<Approvals />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="/procurement" element={<Procurement />} />
        <Route path="/procurement/review/:actionId" element={<OrderReview />} />
        <Route path="/purchase-orders" element={<PurchaseOrders />} />
        <Route path="/purchase-orders/:poId" element={<POThread />} />
        <Route path="/publishing" element={<Publishing />} />
        <Route path="/dunning" element={<Dunning />} />
        <Route path="/suppliers" element={<Suppliers />} />
        <Route path="/intelligence" element={<Intelligence />} />
        <Route path="/barcode" element={<Barcode />} />
        <Route path="/ai-health" element={<AiHealth />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/profile" element={<Profile />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </>
  );
}
