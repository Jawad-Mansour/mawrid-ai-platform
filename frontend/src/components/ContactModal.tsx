// Feature: Supplier & Factory Network — Contact popup. Pick a goal, optionally auto-find
//          the email, and the AI drafts a first-contact email queued for HITL approval —
//          without leaving the map/cards. Shows the company logo + details.
// API:     POST /network/find-email · POST /network/outreach · POST /hitl/actions/{id}/approve
import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { X, Mail, Sparkles, Send, ShieldCheck, CheckCircle2, Search as SearchIcon, Building2, MapPin, Globe } from "lucide-react";
import { toast } from "sonner";
import { apiPost, apiErr } from "@/lib/api";
import { brandLogoSources } from "@/lib/utils";
import { Spinner } from "@/components/ui";

export interface ContactTarget {
  id: string; name: string; category?: string | null; website?: string | null; logo_url?: string | null;
  email?: string | null; city?: string | null; country?: string | null; offering?: string | null;
}

const INTENTS = [
  { key: "general", label: "General enquiry", hint: "Learn about the company, what they make & their export terms" },
  { key: "catalog", label: "Request catalogue", hint: "Ask for their products, available models, quantities & prices" },
  { key: "introduce", label: "Introduce us", hint: "Present our company and propose a partnership" },
];

function Logo({ t }: { t: ContactTarget }) {
  const sources = brandLogoSources(t.logo_url, t.website);
  const [i, setI] = useState(0);
  const src = sources[i];
  if (!src) return <span className="text-lg font-800 text-grape-soft">{t.name[0]?.toUpperCase()}</span>;
  return <img src={src} alt="" className="h-full w-full object-contain p-1.5" onError={() => setI((x) => x + 1)} />;
}

export function ContactModal({ target, onClose }: { target: ContactTarget; onClose: () => void }) {
  const qc = useQueryClient();
  const [intent, setIntent] = useState("general");
  const [email, setEmail] = useState(target.email ?? "");
  const [draft, setDraft] = useState<{ subject: string; body: string; action_id: string } | null>(null);
  const [sent, setSent] = useState(false);
  const loc = [target.city, target.country].filter(Boolean).join(", ");

  const findEmail = useMutation({
    mutationFn: () => apiPost<{ email: string | null }>("/network/find-email", { target_id: target.id }),
    onSuccess: (r) => { if (r.email) { setEmail(r.email); toast.success(`Found: ${r.email}`); } else toast.error("No public email found — type one."); },
    onError: (e) => toast.error(apiErr(e, "Lookup failed")),
  });
  const create = useMutation({
    mutationFn: () => apiPost<{ action_id: string; subject: string; body: string }>("/network/outreach", { target_id: target.id, intent, to: email || null }),
    onSuccess: (r) => { setDraft({ subject: r.subject, body: r.body, action_id: r.action_id }); toast.success("Drafted & queued in HITL Approvals"); qc.invalidateQueries({ queryKey: ["conversations"] }); },
    onError: (e) => toast.error(apiErr(e, "Could not draft")),
  });
  const approve = useMutation({
    mutationFn: () => apiPost(`/hitl/actions/${draft!.action_id}/approve`, {}),
    onSuccess: () => { setSent(true); toast.success("Approved & sent"); },
    onError: (e) => toast.error(apiErr(e, "Send failed")),
  });

  return (
    <AnimatePresence>
      <motion.div className="fixed inset-0 z-[95] grid place-items-center bg-black/60 p-4 backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
        <motion.div className="card relative max-h-[90vh] w-full max-w-lg overflow-y-auto p-6"
          initial={{ scale: 0.96, y: 16, opacity: 0 }} animate={{ scale: 1, y: 0, opacity: 1 }} exit={{ scale: 0.96, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}>
          <button onClick={onClose} className="absolute right-4 top-4 grid h-8 w-8 place-items-center rounded-lg bg-black/20 text-ink hover:bg-black/40"><X className="h-4 w-4" /></button>

          {/* company header */}
          <div className="flex items-center gap-3">
            <div className="grid h-14 w-14 shrink-0 place-items-center overflow-hidden rounded-2xl bg-white" style={{ boxShadow: "0 0 18px rgb(var(--accent) / 0.25)" }}><Logo t={target} /></div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5 text-lg font-800 text-ink"><Building2 className="h-4 w-4 text-gold-soft" /> {target.name}</div>
              <div className="flex flex-wrap items-center gap-x-3 text-xs capitalize text-ink-faint">
                {target.category && <span>{target.category.replace("-", " ")}</span>}
                {loc && <span className="flex items-center gap-1"><MapPin className="h-3 w-3" /> {loc}</span>}
                {target.website && <a href={/^https?:\/\//.test(target.website) ? target.website : `https://${target.website}`} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} className="flex items-center gap-1 text-grape-soft hover:underline"><Globe className="h-3 w-3" /> website</a>}
              </div>
            </div>
          </div>
          {target.offering && <p className="mt-2 text-xs text-ink-soft">{target.offering}</p>}

          {!draft ? (
            <div className="mt-5 space-y-4">
              <div>
                <label className="label">What's the goal?</label>
                <div className="flex flex-wrap gap-2">
                  {INTENTS.map((it) => (
                    <button key={it.key} onClick={() => setIntent(it.key)} title={it.hint}
                      className={`chip ${intent === it.key ? "border-gold/50 bg-gold/15 text-gold-soft" : "border-line bg-white/[0.02] text-ink-soft hover:text-ink"}`}>{it.label}</button>
                  ))}
                </div>
                <p className="mt-1 text-[11px] text-ink-faint">{INTENTS.find((i) => i.key === intent)?.hint}</p>
              </div>
              <div>
                <label className="label">Their email</label>
                <div className="flex gap-2">
                  <input className="input flex-1" type="email" placeholder="auto-find or type one (for testing)" value={email} onChange={(e) => setEmail(e.target.value)} />
                  <button type="button" onClick={() => findEmail.mutate()} disabled={findEmail.isPending} className="btn-ghost shrink-0 !py-2.5" title="Find their public email">
                    {findEmail.isPending ? <Spinner className="h-4 w-4" /> : <SearchIcon className="h-4 w-4" />}
                  </button>
                </div>
                <p className="mt-1 text-[11px] text-ink-faint">Leave blank to auto-find, or set a specific address.</p>
              </div>
              <button className="btn-gold w-full" disabled={create.isPending} onClick={() => create.mutate()}>
                {create.isPending ? <Spinner className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />} Draft &amp; queue for approval
              </button>
            </div>
          ) : (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mt-5">
              <div className="-mx-6 mb-3 flex items-center justify-between bg-gradient-to-r from-gold/15 to-grape/15 px-6 py-2.5">
                <span className="flex items-center gap-2 text-sm font-700 text-ink"><Sparkles className="h-4 w-4 text-gold-soft" /> Draft ready</span>
                <span className={`chip ${sent ? "border-emerald/40 bg-emerald/15 text-emerald-soft" : "border-grape/30 bg-grape/10 text-grape-soft"}`}>{sent ? <><CheckCircle2 className="h-3 w-3" /> Sent</> : "Queued in HITL"}</span>
              </div>
              <div className="text-xs text-ink-faint">Subject: {draft.subject}</div>
              <div className="mt-2 max-h-[220px] overflow-y-auto whitespace-pre-wrap rounded-xl border border-line bg-black/20 p-3 text-sm text-ink">{draft.body}</div>
              {!sent ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  <button className="btn-gold" disabled={approve.isPending} onClick={() => approve.mutate()}>{approve.isPending ? <Spinner className="h-4 w-4" /> : <Send className="h-4 w-4" />} Approve &amp; send now</button>
                  <Link to="/approvals" onClick={onClose} className="btn-ghost"><ShieldCheck className="h-4 w-4" /> Review in HITL</Link>
                </div>
              ) : (
                <div className="mt-4 flex items-center gap-2 rounded-xl border border-emerald/30 bg-emerald/10 p-3 text-sm text-emerald-soft"><CheckCircle2 className="h-4 w-4" /> Sent — track the reply in Discover &amp; Outreach.</div>
              )}
            </motion.div>
          )}

          <div className="mt-4 flex items-center justify-center gap-1 text-[11px] text-ink-faint"><Mail className="h-3 w-3" /> The AI drafts only — nothing sends until you approve.</div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
