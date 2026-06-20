// Feature: Supplier & Factory Network — outreach. AI drafts a professional
//          intro/inquiry email to a factory/supplier; it's queued in HITL
//          Approvals; once approved it sends. Replies are tracked here.
// API:     POST /network/outreach · GET/POST /network/outreach/{id}{,/messages,/reply}
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Sparkles, Send, Inbox, ShieldCheck, ArrowLeft, UploadCloud, MessageSquarePlus, CheckCircle2, Search as SearchIcon, GitCompare, Globe, Building2 } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiErr } from "@/lib/api";
import { SectionTitle, Card, Loading, Spinner } from "@/components/ui";
import { MessageAttachments, type MsgAttachment } from "@/components/MessageAttachments";
import { brandLogoSources } from "@/lib/utils";
import { useNetwork } from "@/stores/network";

interface Pin { id: string; name: string; category: string; website?: string | null; logo_url?: string | null }
function CompanyLogo({ url, website, name }: { url?: string | null; website?: string | null; name: string }) {
  const sources = brandLogoSources(url, website);
  const [i, setI] = useState(0);
  const src = sources[i];
  if (!src) return <span className="text-base font-800 text-grape-soft">{name[0]?.toUpperCase()}</span>;
  return <img src={src} alt="" className="h-full w-full object-contain p-1.5" onError={() => setI((x) => x + 1)} />;
}

interface Msg { direction: string; sender: string; body: string; at: string; attachments?: MsgAttachment[] }
interface ThreadData { supplier_id: string; name: string; email: string | null; messages: Msg[] }
const INTENTS = [
  { key: "introduce", label: "Introduce us", hint: "Present our company & propose a partnership" },
  { key: "catalog", label: "Request catalogue", hint: "Ask for their products, quantities & prices" },
  { key: "general", label: "General enquiry", hint: "Learn more about the company & terms" },
];

export function Outreach() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const net = useNetwork();
  const target = params.get("target");
  const [supplierId, setSupplierId] = useState<string | null>(params.get("supplier"));
  const factories = useQuery({ queryKey: ["factories", "europe"], queryFn: () => apiGet<{ pins: Pin[] }>("/network/factories?region=europe"), staleTime: 60_000 });
  const targetPin = (factories.data?.pins ?? []).find((p) => p.id === target) ?? null;
  const goCompare = () => { if (target && !net.has(target)) net.toggle(target); navigate("/suppliers/compare"); };
  const [intent, setIntent] = useState("introduce");
  const [notes, setNotes] = useState("");
  const [email, setEmail] = useState("");
  const [draft, setDraft] = useState<{ subject: string; body: string; action_id: string } | null>(null);

  const [sent, setSent] = useState(false);
  const create = useMutation({
    mutationFn: () => apiPost<{ supplier_id: string; action_id: string; to: string | null; subject: string; body: string }>("/network/outreach", { target_id: target, intent, notes: notes || null, to: email || null }),
    onSuccess: (r) => { setSupplierId(r.supplier_id); setDraft({ subject: r.subject, body: r.body, action_id: r.action_id }); toast.success("Drafted & queued in HITL Approvals"); },
    onError: (e) => toast.error(apiErr(e, "Could not draft")),
  });
  const findEmail = useMutation({
    mutationFn: () => apiPost<{ email: string | null }>("/network/find-email", { target_id: target }),
    onSuccess: (r) => { if (r.email) { setEmail(r.email); toast.success(`Found: ${r.email}`); } else toast.error("No public email found — enter one manually."); },
    onError: (e) => toast.error(apiErr(e, "Lookup failed")),
  });
  const approveNow = useMutation({
    mutationFn: () => apiPost(`/hitl/actions/${draft!.action_id}/approve`, {}),
    onSuccess: () => { setSent(true); toast.success("Approved & sent"); qc.invalidateQueries({ queryKey: ["conversations"] }); },
    onError: (e) => toast.error(apiErr(e, "Send failed")),
  });

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <SectionTitle title="Supplier Outreach" subtitle="The AI writes a professional first email; approve it in HITL to send, then track the reply."
        right={<div className="flex gap-2">
          <button onClick={goCompare} className="btn-ghost !py-2" title="Compare this supplier with others"><GitCompare className="h-4 w-4" /> Compare</button>
          <Link to="/suppliers/network" className="btn-ghost !py-2"><ArrowLeft className="h-4 w-4" /> Network</Link>
        </div>} />

      {/* the company we're contacting — logo + name */}
      {targetPin && (
        <Card className="flex items-center gap-3">
          <div className="grid h-14 w-14 shrink-0 place-items-center overflow-hidden rounded-2xl bg-white" style={{ boxShadow: "0 0 18px rgb(var(--accent) / 0.25)" }}>
            <CompanyLogo url={targetPin.logo_url} website={targetPin.website} name={targetPin.name} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 text-base font-800 text-ink"><Building2 className="h-4 w-4 text-gold-soft" /> {targetPin.name}</div>
            <div className="flex items-center gap-2 text-xs capitalize text-ink-faint">
              {targetPin.category?.replace("-", " ")}
              {targetPin.website && <a href={/^https?:\/\//.test(targetPin.website) ? targetPin.website : `https://${targetPin.website}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-grape-soft hover:underline"><Globe className="h-3 w-3" /> website</a>}
            </div>
          </div>
          <button onClick={goCompare} className="chip border-grape/30 bg-grape/10 text-grape-soft hover:bg-grape/20"><GitCompare className="h-3.5 w-3.5" /> Compare</button>
        </Card>
      )}

      {/* compose (only when starting from a target and not yet drafted) */}
      {target && !draft && (
        <Card>
          <SectionTitle title="Compose with AI" right={<Sparkles className="h-5 w-5 text-grape-soft" />} />
          <div className="space-y-3">
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
                <input className="input flex-1" type="email" placeholder="auto-find or type a specific one (for testing)" value={email} onChange={(e) => setEmail(e.target.value)} />
                <button type="button" onClick={() => findEmail.mutate()} disabled={findEmail.isPending} className="btn-ghost shrink-0 !py-2.5" title="Search the web for their contact email">{findEmail.isPending ? <Spinner className="h-4 w-4" /> : <SearchIcon className="h-4 w-4" />} Auto-find</button>
              </div>
              <p className="mt-1 text-[11px] text-ink-faint">Leave blank to auto-find, or type a specific address you want to send to (handy for testing).</p>
            </div>
            <div><label className="label">Anything to add? (optional)</label><textarea className="input min-h-[70px] resize-y" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="e.g. we focus on built-in appliances for the Lebanese market" /></div>
            <button className="btn-gold" disabled={create.isPending} onClick={() => create.mutate()}>{create.isPending ? <Spinner className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />} Draft & queue for approval</button>
          </div>
        </Card>
      )}

      {/* drafting animation */}
      {create.isPending && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center gap-3 py-6">
          <motion.div className="grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-gold to-grape shadow-glow" animate={{ rotate: 360 }} transition={{ duration: 1.4, repeat: Infinity, ease: "linear" }}><Sparkles className="h-6 w-6 text-bg" /></motion.div>
          <div className="text-sm text-ink-soft">The AI is writing a professional first email…</div>
        </motion.div>
      )}

      {/* drafted confirmation — approve here or in HITL */}
      {draft && (
        <motion.div initial={{ opacity: 0, y: 10, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ type: "spring", stiffness: 200, damping: 20 }}>
          <Card className="overflow-hidden">
            <div className="-m-5 mb-4 flex items-center justify-between gap-2 bg-gradient-to-r from-gold/15 to-grape/15 px-5 py-3">
              <span className="flex items-center gap-2 text-sm font-700 text-ink"><Sparkles className="h-4 w-4 text-gold-soft" /> Draft ready</span>
              <span className={`chip ${sent ? "border-emerald/40 bg-emerald/15 text-emerald-soft" : "border-grape/30 bg-grape/10 text-grape-soft"}`}>{sent ? <><CheckCircle2 className="h-3 w-3" /> Sent</> : "Queued in HITL"}</span>
            </div>
            <div className="text-xs text-ink-faint">Subject: {draft.subject}</div>
            <div className="mt-2 max-h-[280px] overflow-y-auto whitespace-pre-wrap rounded-xl border border-line bg-black/20 p-4 text-sm text-ink">{draft.body}</div>
            {!sent ? (
              <div className="mt-4 flex flex-wrap gap-2">
                <button className="btn-gold" disabled={approveNow.isPending} onClick={() => approveNow.mutate()}>{approveNow.isPending ? <Spinner className="h-4 w-4" /> : <Send className="h-4 w-4" />} Approve & send now</button>
                <Link to="/approvals" className="btn-ghost"><ShieldCheck className="h-4 w-4" /> Review in HITL</Link>
              </div>
            ) : (
              <div className="mt-4 flex items-center gap-2 rounded-xl border border-emerald/30 bg-emerald/10 p-3 text-sm text-emerald-soft"><CheckCircle2 className="h-4 w-4" /> Sent — track replies in the conversation below or the Outreach Inbox.</div>
            )}
          </Card>
        </motion.div>
      )}

      {/* reply thread */}
      {supplierId && <Thread supplierId={supplierId} onEnrich={() => navigate(`/upload?supplier=${supplierId}`)} qc={qc} />}

      {!target && !supplierId && (
        <Card><div className="py-10 text-center text-ink-soft">Open the <Link to="/suppliers/network" className="text-gold-soft underline">Network map</Link> and hit <b>Contact</b> on a factory to start.</div></Card>
      )}
    </div>
  );
}

function Thread({ supplierId, onEnrich, qc }: { supplierId: string; onEnrich: () => void; qc: ReturnType<typeof useQueryClient> }) {
  const [log, setLog] = useState("");
  const [reply, setReply] = useState("");
  const t = useQuery({ queryKey: ["outreach", supplierId], queryFn: () => apiGet<ThreadData>(`/network/outreach/${supplierId}`), refetchInterval: 10_000 });
  const invalidate = () => qc.invalidateQueries({ queryKey: ["outreach", supplierId] });
  const logReply = useMutation({ mutationFn: () => apiPost(`/network/outreach/${supplierId}/messages`, { body: log, direction: "inbound" }), onSuccess: () => { setLog(""); toast.success("Reply logged"); invalidate(); }, onError: (e) => toast.error(apiErr(e, "Failed")) });
  const sendReply = useMutation({ mutationFn: () => apiPost(`/network/outreach/${supplierId}/reply`, { body: reply }), onSuccess: () => { setReply(""); toast.success("Reply sent"); invalidate(); }, onError: (e) => toast.error(apiErr(e, "Send failed")) });
  const d = t.data;

  return (
    <>
      <Card>
        <SectionTitle title="Conversation" subtitle={d ? `${d.name}${d.email ? " · " + d.email : ""}` : ""} right={<button onClick={onEnrich} className="chip border-grape/30 bg-grape/10 text-grape-soft hover:bg-grape/20"><UploadCloud className="h-3.5 w-3.5" /> Use for enrichment</button>} />
        {t.isLoading ? <Loading /> : (
          <div className="space-y-3">
            {(d?.messages ?? []).length === 0 && <p className="py-4 text-center text-sm text-ink-faint">No messages yet — approve the draft in HITL to send the first one.</p>}
            {(d?.messages ?? []).map((m, i) => {
              const out = m.direction === "outbound";
              return (
                <div key={i} className={`flex gap-3 ${out ? "flex-row-reverse" : ""}`}>
                  <div className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg ${out ? "bg-gold text-bg" : "bg-grape/20 text-grape-soft"}`}>{out ? <Send className="h-4 w-4" /> : <Inbox className="h-4 w-4" />}</div>
                  <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${out ? "rounded-tr-sm bg-gold/15" : "rounded-tl-sm border border-line bg-bg-soft"}`}>
                    <div className="mb-1 text-[11px] text-ink-faint"><span className="font-700 text-ink-soft">{m.sender}</span> · {new Date(m.at).toLocaleString()}</div>
                    <div className="whitespace-pre-wrap leading-relaxed text-ink-soft">{m.body}</div>
                    {!out && <MessageAttachments attachments={m.attachments} supplierId={supplierId} supplierName={d?.name} />}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <Card>
        <SectionTitle title="Log a reply received" right={<MessageSquarePlus className="h-5 w-5 text-ink-faint" />} />
        <textarea className="input min-h-[70px] resize-y" placeholder="Paste the supplier's reply…" value={log} onChange={(e) => setLog(e.target.value)} />
        <button className="btn-ghost mt-2" disabled={!log.trim() || logReply.isPending} onClick={() => logReply.mutate()}>{logReply.isPending ? <Spinner className="h-4 w-4" /> : <Inbox className="h-4 w-4" />} Log reply</button>
      </Card>

      <Card>
        <SectionTitle title="Reply to supplier" right={<ShieldCheck className="h-5 w-5 text-ink-faint" />} />
        <textarea className="input min-h-[100px] resize-y" placeholder="Write a reply…" value={reply} onChange={(e) => setReply(e.target.value)} />
        <button className="btn-gold mt-2" disabled={!reply.trim() || !d?.email || sendReply.isPending} onClick={() => sendReply.mutate()}>{sendReply.isPending ? <Spinner className="h-4 w-4" /> : <Send className="h-4 w-4" />} Send reply</button>
        {!d?.email && <p className="mt-2 text-xs text-warn">⚠ No email on file for this supplier.</p>}
      </Card>
    </>
  );
}
