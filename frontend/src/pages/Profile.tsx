// Feature: Profile — avatar upload + display name + account details.
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Camera, Trash2, User, Mail, Building2, ShieldCheck, Save, Globe, Check } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/hooks/useAuth";
import { useProfile } from "@/stores/profile";
import { Card, SectionTitle } from "@/components/ui";

export function Profile() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { avatar, displayName, title, setAvatar, setDisplayName, setTitle } = useProfile();
  const fileRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState(displayName);
  const [role, setRole] = useState(title);
  const [saved, setSaved] = useState(false);

  function handleSave() {
    setDisplayName(name);
    setTitle(role);
    setSaved(true);
    // brief success animation, then return to wherever the user came from
    setTimeout(() => navigate(-1), 1100);
  }

  function pickAvatar(file: File | undefined) {
    if (!file) return;
    if (!file.type.startsWith("image/")) { toast.error("Please choose an image file."); return; }
    if (file.size > 2_500_000) { toast.error("Image is too large (max ~2.5 MB)."); return; }
    const reader = new FileReader();
    reader.onload = () => { setAvatar(String(reader.result)); toast.success("Profile photo updated"); };
    reader.readAsDataURL(file);
  }

  const initials = (name || user?.email || "M")[0]?.toUpperCase();

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <AnimatePresence>
        {saved && (
          <motion.div className="fixed inset-0 z-[100] grid place-items-center bg-page/80 backdrop-blur-md" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <motion.div className="flex flex-col items-center gap-3" initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: "spring", stiffness: 200, damping: 14 }}>
              <div className="grid h-20 w-20 place-items-center rounded-full bg-gradient-to-br from-emerald to-emerald-soft shadow-glow">
                <Check className="h-10 w-10 text-white" />
              </div>
              <div className="text-lg font-800 text-ink">Profile saved</div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <SectionTitle title="Profile" subtitle="Your photo and details across Mawrid." />

      <Card>
        <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-start">
          {/* avatar */}
          <div className="relative">
            <div className="grid h-28 w-28 place-items-center overflow-hidden rounded-3xl bg-gradient-to-br from-grape to-gold text-4xl font-800 text-bg shadow-glow">
              {avatar ? <img src={avatar} alt="" className="h-full w-full object-cover" /> : initials}
            </div>
            <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={(e) => { pickAvatar(e.target.files?.[0]); e.target.value = ""; }} />
            <button onClick={() => fileRef.current?.click()} className="absolute -bottom-1 -right-1 grid h-9 w-9 place-items-center rounded-xl border border-line bg-bg shadow-glow hover:bg-gold/10" title="Change photo">
              <Camera className="h-4 w-4 text-gold-soft" />
            </button>
          </div>

          <div className="flex-1 space-y-3">
            <div>
              <label className="label"><User className="mr-1 inline h-3.5 w-3.5" /> Display name</label>
              <input className="input" placeholder="e.g. Jawad M." value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div>
              <label className="label">Title / role</label>
              <input className="input" placeholder="e.g. Operations Lead" value={role} onChange={(e) => setRole(e.target.value)} />
            </div>
            <div className="flex gap-2">
              <button className="btn-gold" onClick={handleSave}><Save className="h-4 w-4" /> Save</button>
              {avatar && <button className="btn-ghost" onClick={() => setAvatar(null)}><Trash2 className="h-4 w-4" /> Remove photo</button>}
            </div>
          </div>
        </div>
      </Card>

      <Card>
        <SectionTitle title="Account" subtitle="From your workspace — read-only." />
        <dl className="grid gap-3 sm:grid-cols-2">
          {[
            { icon: Mail, k: "Email", v: user?.email },
            { icon: ShieldCheck, k: "Role", v: user?.role },
            { icon: Building2, k: "Tenant", v: user?.tenant_id },
            { icon: Globe, k: "Operational mode", v: user?.operational_mode?.replace("_", " ") },
          ].map((r) => (
            <div key={r.k} className="rounded-xl border border-line bg-white/[0.02] p-3">
              <div className="flex items-center gap-1.5 text-xs text-ink-faint"><r.icon className="h-3.5 w-3.5" /> {r.k}</div>
              <div className="mt-0.5 truncate font-mono text-sm text-ink">{r.v ?? "—"}</div>
            </div>
          ))}
        </dl>
      </Card>
    </div>
  );
}
