// Feature: Intelligence — AI Assistant. One chatbot, two roles you pick per message:
//          Advisor (business/financial advice) and Command Center (factual Q&A grounded
//          on your live data). Multilingual (EN/FR/AR). Orb UI, theme-coloured.
// API:     POST /assistant/chat
import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { Send, Sparkles, Lightbulb, Database, Languages, MessageSquare } from "lucide-react";
import { apiPost, apiErr } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Spinner } from "@/components/ui";
import { Markdown } from "@/components/Markdown";

type Role = "advisor" | "command_center";
interface Msg { who: "user" | "bot"; text: string; role?: Role }

const SUGGEST: Record<Role, string[]> = {
  command_center: ["How many products do I have in stock?", "How many fridges vs toasters?", "What's awaiting HITL approval?", "Total value of my purchase orders?"],
  advisor: ["How can I improve my cash flow?", "Which supplier should I rely on most?", "How do I handle a supplier that delivered damaged goods?", "What should I focus on this week?"],
};

export function Intelligence() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [role, setRole] = useState<Role>("advisor");
  const [lang, setLang] = useState("en");
  const [busy, setBusy] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const location = useLocation();
  const seeded = useRef(false);

  useEffect(() => { listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" }); }, [msgs, busy]);

  async function send(text: string, asRole: Role = role) {
    const t = text.trim();
    if (!t || busy) return;
    setMsgs((m) => [...m, { who: "user", text: t, role: asRole }]);
    setQ(""); setBusy(true);
    try {
      const history = msgs.slice(-8).map((m) => ({ role: m.who === "user" ? "user" : "assistant", content: m.text }));
      const r = await apiPost<{ answer: string; role: Role }>("/assistant/chat", { role: asRole, message: t, history, lang });
      setMsgs((m) => [...m, { who: "bot", text: r.answer, role: asRole }]);
    } catch (e) {
      setMsgs((m) => [...m, { who: "bot", text: apiErr(e, "I couldn't reach the assistant."), role: asRole }]);
    } finally { setBusy(false); }
  }

  // seed from "Ask in AI Assistant" handoff
  useEffect(() => {
    const seed = (location.state as any)?.seed;
    if (seed && !seeded.current) { seeded.current = true; setRole("command_center"); send(seed, "command_center"); }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const empty = msgs.length === 0;

  return (
    <div className="mx-auto flex h-[calc(100vh-7rem)] max-w-3xl flex-col">
      {/* orb hero (only when empty) */}
      {empty && (
        <div className="flex flex-1 flex-col items-center justify-center gap-5 text-center">
          <Orb />
          <div>
            <div className="text-2xl font-800 text-ink">Ready to help you decide</div>
            <div className="mt-1 text-sm text-ink-soft">Ask for <b>advice</b>, or anything about your <b>command center</b> — in English, Français or العربية.</div>
          </div>
          <div className="flex flex-wrap justify-center gap-2">
            {SUGGEST[role].map((s) => (
              <button key={s} onClick={() => send(s)} className="chip border-line bg-white/[0.03] text-ink-soft hover:border-gold/40 hover:text-ink">{s}</button>
            ))}
          </div>
        </div>
      )}

      {/* messages */}
      {!empty && (
        <div ref={listRef} className="flex-1 space-y-4 overflow-y-auto py-4">
          {msgs.map((m, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className={cn("flex gap-3", m.who === "user" && "flex-row-reverse")}>
              <div className={cn("grid h-8 w-8 shrink-0 place-items-center rounded-lg", m.who === "user" ? "bg-gold text-bg" : "bg-gradient-to-br from-gold to-grape text-bg")}>
                {m.who === "user" ? <MessageSquare className="h-4 w-4" /> : m.role === "command_center" ? <Database className="h-4 w-4" /> : <Lightbulb className="h-4 w-4" />}
              </div>
              <div className={cn("max-w-[82%] rounded-2xl px-4 py-2.5 text-sm", m.who === "user" ? "rounded-tr-sm bg-gold/15 text-ink" : "rounded-tl-sm border border-line bg-bg-soft")}>
                {m.who === "user" ? <span className="whitespace-pre-wrap">{m.text}</span> : <Markdown>{m.text}</Markdown>}
                {m.who === "bot" && m.role === "command_center" && (
                  <button onClick={() => send(`Based on this, advise me: ${m.text}`, "advisor")} className="mt-2 chip border-grape/30 bg-grape/10 text-grape-soft hover:bg-grape/20"><Lightbulb className="h-3 w-3" /> Ask the advisor about this</button>
                )}
              </div>
            </motion.div>
          ))}
          {busy && <div className="flex items-center gap-2 text-sm text-ink-soft"><Spinner className="h-4 w-4" /> Thinking…</div>}
        </div>
      )}

      {/* input with role + language selectors */}
      <div className="rounded-2xl border border-line bg-bg-card p-3 shadow-glass backdrop-blur">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <div className="flex gap-1 rounded-xl border border-line bg-white/[0.02] p-0.5">
            {([{ k: "advisor", label: "Advisor", icon: Lightbulb }, { k: "command_center", label: "Command Center", icon: Database }] as const).map((r) => (
              <button key={r.k} onClick={() => setRole(r.k)} className={cn("flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-600 transition-all", role === r.k ? "bg-gold/15 text-gold-soft" : "text-ink-soft hover:text-ink")}>
                <r.icon className="h-3.5 w-3.5" /> {r.label}
              </button>
            ))}
          </div>
          <div className="ml-auto flex items-center gap-1.5 text-ink-faint">
            <Languages className="h-3.5 w-3.5" />
            <select value={lang} onChange={(e) => setLang(e.target.value)} className="rounded-lg border border-line bg-transparent px-2 py-1 text-xs text-ink-soft outline-none">
              <option value="en">English</option><option value="fr">Français</option><option value="ar">العربية</option>
            </select>
          </div>
        </div>
        <form onSubmit={(e) => { e.preventDefault(); send(q); }} className="flex gap-2">
          <input className="input" placeholder={role === "advisor" ? "Ask for business or financial advice…" : "Ask anything about your data…"} value={q} onChange={(e) => setQ(e.target.value)} />
          <button type="submit" disabled={busy || !q.trim()} className="btn-gold !px-3.5">{busy ? <Spinner className="h-4 w-4" /> : <Send className="h-4 w-4" />}</button>
        </form>
        <p className="mt-1.5 text-center text-[11px] text-ink-faint">{role === "advisor" ? "Advisor — strategy & decisions, grounded on your live business." : "Command Center — factual answers from your real data."}</p>
      </div>
    </div>
  );
}

// The orb: a living, theme-coloured sphere (uses --accent so it recolours with the theme).
function Orb() {
  return (
    <div className="relative grid h-40 w-40 place-items-center">
      <motion.div className="absolute inset-0 rounded-full blur-2xl" style={{ background: "rgb(var(--accent))", opacity: 0.35 }}
        animate={{ scale: [1, 1.15, 1], opacity: [0.3, 0.5, 0.3] }} transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }} />
      <motion.div className="relative h-28 w-28 overflow-hidden rounded-full"
        style={{ background: "radial-gradient(circle at 32% 28%, rgba(255,255,255,0.85), rgb(var(--accent)) 45%, rgba(0,0,0,0.55) 100%)", boxShadow: "0 0 50px rgb(var(--accent))" }}
        animate={{ scale: [1, 1.04, 1] }} transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}>
        <motion.div className="absolute -inset-6 opacity-40" style={{ background: "conic-gradient(from 0deg, transparent, rgba(255,255,255,0.6), transparent)" }}
          animate={{ rotate: 360 }} transition={{ duration: 8, repeat: Infinity, ease: "linear" }} />
        <Sparkles className="absolute left-1/2 top-1/2 h-6 w-6 -translate-x-1/2 -translate-y-1/2 text-white/90" />
      </motion.div>
    </div>
  );
}
