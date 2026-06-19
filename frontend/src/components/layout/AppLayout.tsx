// Feature: Layout — authenticated app shell
import { useState } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { Background } from "@/components/Background";
import { useAuthStore } from "@/stores/auth";
import { Loading } from "@/components/ui";

export function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const { user, ready } = useAuthStore();

  if (!ready) return <div className="grid h-screen place-items-center"><Loading label="Starting Mawrid…" /></div>;
  if (!user) return <Navigate to="/login" replace />;

  return (
    <div className="flex min-h-screen bg-radial-fade">
      <Background />
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="flex-1 px-4 py-6 md:px-8">
          <div className="mx-auto max-w-[1400px]">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
