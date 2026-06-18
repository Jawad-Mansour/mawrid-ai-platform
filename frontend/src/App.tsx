import { Routes, Route, Navigate } from "react-router-dom";
import { useBootstrapAuth } from "@/hooks/useAuth";
import { useApplyTheme } from "@/stores/theme";
import { LogoutOverlay } from "@/components/LogoutOverlay";
import { Intelligence } from "@/pages/Intelligence";
import { Suppliers } from "@/pages/Suppliers";
import { Network } from "@/pages/network/Network";
import { Compare } from "@/pages/network/Compare";
import { Outreach } from "@/pages/network/Outreach";
import { OutreachInbox } from "@/pages/network/OutreachInbox";
import { EditOrder } from "@/pages/procurement/EditOrder";
import { Shipments } from "@/pages/inventory/Shipments";
import { Receive } from "@/pages/inventory/Receive";
import { Stock } from "@/pages/inventory/Stock";
import { Demand } from "@/pages/inventory/Demand";
import { SupplierDunning } from "@/pages/dunning/SupplierDunning";
import { CustomerDunning } from "@/pages/dunning/CustomerDunning";
import { AppLayout } from "@/components/layout/AppLayout";
import { ChooseMode } from "@/pages/auth/ChooseMode";
import { Signup } from "@/pages/auth/Signup";
import { Login } from "@/pages/auth/Login";
import { Dashboard } from "@/pages/Dashboard";
import { UploadPage } from "@/pages/UploadPage";
import { UploadHistory } from "@/pages/UploadHistory";
import { NeedsReview } from "@/pages/NeedsReview";
import { NotificationsPage } from "@/pages/NotificationsPage";
import { Activity } from "@/pages/Activity";
import { Profile } from "@/pages/Profile";
import { Catalog } from "@/pages/Catalog";
import { Approvals } from "@/pages/Approvals";
import { Procurement } from "@/pages/Procurement";
import { OrderReview } from "@/pages/OrderReview";
import { PurchaseOrders } from "@/pages/PurchaseOrders";
import { POThread } from "@/pages/POThread";
import { SupplierReplies } from "@/pages/SupplierReplies";
import { Publishing } from "@/pages/Publishing";
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
        <Route path="/activity" element={<Activity />} />
        <Route path="/procurement" element={<Procurement />} />
        <Route path="/procurement/review/:actionId" element={<OrderReview />} />
        <Route path="/purchase-orders" element={<PurchaseOrders />} />
        <Route path="/purchase-orders/:poId" element={<POThread />} />
        <Route path="/procurement/edit/:poId" element={<EditOrder />} />
        <Route path="/supplier-replies" element={<SupplierReplies />} />
        <Route path="/publishing" element={<Publishing />} />
        <Route path="/dunning" element={<SupplierDunning />} />
        <Route path="/dunning/customer" element={<CustomerDunning />} />
        <Route path="/suppliers" element={<Suppliers relationship="active" />} />
        <Route path="/suppliers/prospects" element={<Suppliers relationship="prospect" />} />
        <Route path="/suppliers/network" element={<Network />} />
        <Route path="/suppliers/compare" element={<Compare />} />
        <Route path="/suppliers/outreach" element={<Outreach />} />
        <Route path="/suppliers/inbox" element={<OutreachInbox />} />
        <Route path="/inventory/shipments" element={<Shipments />} />
        <Route path="/inventory/receive" element={<Receive />} />
        <Route path="/inventory/stock" element={<Stock />} />
        <Route path="/inventory/demand" element={<Demand />} />
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
