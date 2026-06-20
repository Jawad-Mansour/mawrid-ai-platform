// Feature: Intelligence — AI Assistant. One chatbot, two roles you pick per message:
//          Advisor (business/financial advice) and Command Center (factual Q&A grounded
//          on your live data). Multilingual (EN/FR/AR). Orb UI, theme-coloured.
// API:     POST /assistant/chat
import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { Send, Lightbulb, Database, Languages, MessageSquare, Plus, History, Trash2 } from "lucide-react";
import { apiPost, apiErr } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Spinner } from "@/components/ui";
import { Markdown } from "@/components/Markdown";

type Role = "advisor" | "command_center";
interface Msg { who: "user" | "bot"; text: string; role?: Role }
interface Session { id: string; title: string; msgs: Msg[]; at: number }

const SUGGEST: Record<Role, string[]> = {
  command_center: ["How many products do I have in stock?", "How many fridges vs toasters?", "What's awaiting HITL approval?", "Total value of my purchase orders?"],
  advisor: ["How can I improve my cash flow?", "Which supplier should I rely on most?", "How do I handle a supplier that delivered damaged goods?", "What should I focus on this week?"],
};

const LS = "mawrid_assistant_sessions";
const uid = () => (crypto?.randomUUID?.() ?? String(Date.now() + Math.random()));
function loadSessions(): Session[] {
  try { const s = JSON.parse(localStorage.getItem(LS) || "[]"); return Array.isArray(s) ? s : []; } catch { return []; }
}

export function Intelligence() {
  const [sessions, setSessions] = useState<Session[]>(() => loadSessions());
  const [activeId, setActiveId] = useState<string>(() => loadSessions()[0]?.id ?? "");
  const [showHistory, setShowHistory] = useState(false);
  const [q, setQ] = useState("");
  const [role, setRole] = useState<Role>("advisor");
  const [lang, setLang] = useState("en");
  const [busy, setBusy] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const location = useLocation();
  const seeded = useRef(false);

  // always have at least one session
  useEffect(() => {
    if (sessions.length === 0) { const id = uid(); setSessions([{ id, title: "New chat", msgs: [], at: Date.now() }]); setActiveId(id); }
    else if (!sessions.find((s) => s.id === activeId)) setActiveId(sessions[0].id);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { localStorage.setItem(LS, JSON.stringify(sessions.slice(0, 40))); }, [sessions]);

  const active = sessions.find((s) => s.id === activeId) ?? null;
  const msgs = active?.msgs ?? [];

  useEffect(() => { listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" }); }, [msgs.length, busy]);

  function setMsgsFor(updater: (m: Msg[]) => Msg[]) {
    setSessions((ss) => ss.map((s) => {
      if (s.id !== activeId) return s;
      const nm = updater(s.msgs);
      const title = s.msgs.length === 0 && nm[0]?.who === "user" ? nm[0].text.slice(0, 42) : s.title;
      return { ...s, msgs: nm, at: Date.now(), title };
    }));
  }
  function newChat() { const id = uid(); setSessions((ss) => [{ id, title: "New chat", msgs: [], at: Date.now() }, ...ss]); setActiveId(id); setShowHistory(false); }
  function deleteChat(id: string) { setSessions((ss) => ss.filter((s) => s.id !== id)); if (id === activeId) { const rest = sessions.filter((s) => s.id !== id); setActiveId(rest[0]?.id ?? ""); } }
  function clearAllHistory() {
    if (!confirm("Clear all chat history? This deletes every saved conversation.")) return;
    const id = uid();
    setSessions([{ id, title: "New chat", msgs: [], at: Date.now() }]);
    setActiveId(id); setShowHistory(false);
  }

  async function send(text: string, asRole: Role = role) {
    const t = text.trim();
    if (!t || busy) return;
    setMsgsFor((m) => [...m, { who: "user", text: t, role: asRole }]);
    setQ(""); setBusy(true);
    try {
      const history = msgs.slice(-8).map((m) => ({ role: m.who === "user" ? "user" : "assistant", content: m.text }));
      const r = await apiPost<{ answer: string; role: Role }>("/assistant/chat", { role: asRole, message: t, history, lang });
      setMsgsFor((m) => [...m, { who: "bot", text: r.answer, role: asRole }]);
    } catch (e) {
      setMsgsFor((m) => [...m, { who: "bot", text: apiErr(e, "I couldn't reach the assistant."), role: asRole }]);
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
      {/* top bar: new chat + history */}
      <div className="relative mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-700 text-ink"><Database className="h-4 w-4 text-gold-soft" /> AI Assistant</div>
        <div className="flex items-center gap-2">
          <button onClick={newChat} className="chip border-line bg-white/[0.03] text-ink-soft hover:text-ink"><Plus className="h-3.5 w-3.5" /> New chat</button>
          <button onClick={() => setShowHistory((v) => !v)} className="chip border-line bg-white/[0.03] text-ink-soft hover:text-ink"><History className="h-3.5 w-3.5" /> History {sessions.length > 0 && <span className="text-ink-faint">({sessions.length})</span>}</button>
        </div>
        {showHistory && (
          <>
            <div className="fixed inset-0 z-20" onClick={() => setShowHistory(false)} />
            <div className="absolute right-0 top-9 z-30 max-h-[60vh] w-72 overflow-y-auto rounded-2xl border border-line bg-bg-card p-2 shadow-glass backdrop-blur">
              {sessions.length === 0 && <div className="p-3 text-center text-xs text-ink-faint">No history yet.</div>}
              {[...sessions].sort((a, b) => b.at - a.at).map((s) => (
                <div key={s.id} className={cn("group flex items-center gap-2 rounded-xl px-3 py-2 text-left text-xs transition-colors hover:bg-white/[0.05]", s.id === activeId && "bg-gold/10")}>
                  <button onClick={() => { setActiveId(s.id); setShowHistory(false); }} className="min-w-0 flex-1 text-left">
                    <div className="truncate font-600 text-ink">{s.title || "New chat"}</div>
                    <div className="text-[10px] text-ink-faint">{s.msgs.length} message(s)</div>
                  </button>
                  <button onClick={() => deleteChat(s.id)} className="shrink-0 text-ink-faint opacity-0 transition-opacity hover:text-danger group-hover:opacity-100" title="Delete"><Trash2 className="h-3.5 w-3.5" /></button>
                </div>
              ))}
              {sessions.some((s) => s.msgs.length > 0) && (
                <button onClick={clearAllHistory} className="mt-1 flex w-full items-center justify-center gap-1.5 rounded-xl border border-line px-3 py-2 text-xs text-ink-faint transition-colors hover:border-danger/50 hover:text-danger">
                  <Trash2 className="h-3.5 w-3.5" /> Clear all history
                </button>
              )}
            </div>
          </>
        )}
      </div>

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

// The orb: a living, theme-coloured 3D sphere — swirling "smoke" inside, a tilted orbital
// ring, drifting particles, and a sleepy face whose eyes blink. Recolours with --accent.
const A = (a: number) => `rgb(var(--accent) / ${a})`;

function Eye({ delay }: { delay: number }) {
  return (
    <motion.span
      className="block h-7 w-[11px] rounded-full"
      style={{ background: "rgb(255 255 255 / 0.95)", boxShadow: `0 0 12px ${A(0.9)}, 0 0 4px rgb(255 255 255 / 0.8)`, transformOrigin: "center" }}
      initial={{ scaleY: 0.08 }}
      // wakes up, then blinks (occasional double-blink) forever
      animate={{ scaleY: [0.08, 1, 1, 0.08, 1, 1, 0.08, 0.08, 1, 1] }}
      transition={{ duration: 6.5, times: [0, 0.06, 0.55, 0.6, 0.66, 0.88, 0.92, 0.95, 0.99, 1], repeat: Infinity, repeatDelay: 0.4, delay }}
    />
  );
}

function Orb() {
  return (
    <div className="relative grid h-48 w-48 place-items-center" style={{ perspective: 600 }}>
      {/* pulsing aura */}
      <motion.div
        className="absolute h-44 w-44 rounded-full blur-2xl"
        style={{ background: A(0.4) }}
        animate={{ scale: [1, 1.18, 1], opacity: [0.35, 0.6, 0.35] }}
        transition={{ duration: 4.5, repeat: Infinity, ease: "easeInOut" }}
      />

      {/* drifting particles */}
      {[0, 1, 2, 3, 4].map((i) => (
        <motion.span
          key={i}
          className="absolute h-1 w-1 rounded-full"
          style={{ background: A(0.9), left: `${28 + i * 11}%`, bottom: "30%" }}
          animate={{ y: [0, -34, 0], opacity: [0, 0.9, 0], scale: [0.6, 1, 0.6] }}
          transition={{ duration: 3.5 + i * 0.4, repeat: Infinity, ease: "easeInOut", delay: i * 0.6 }}
        />
      ))}

      {/* the sphere — breathes gently */}
      <motion.div
        className="relative h-28 w-28 overflow-hidden rounded-full"
        style={{
          background: `radial-gradient(circle at 34% 28%, rgb(255 255 255 / 0.9), ${A(0.95)} 42%, rgb(0 0 0 / 0.55) 100%)`,
          boxShadow: `0 0 60px ${A(0.8)}, inset -8px -10px 26px rgb(0 0 0 / 0.5), inset 6px 8px 20px rgb(255 255 255 / 0.25)`,
        }}
        animate={{ scale: [1, 1.045, 1] }}
        transition={{ duration: 3.4, repeat: Infinity, ease: "easeInOut" }}
      >
        {/* swirling smoke (two counter-rotating blurred layers) */}
        <motion.div
          className="absolute -inset-8 opacity-50 blur-md"
          style={{ background: `conic-gradient(from 0deg, transparent, rgb(255 255 255 / 0.55), transparent 40%, ${A(0.7)} 60%, transparent 80%)` }}
          animate={{ rotate: 360 }}
          transition={{ duration: 7, repeat: Infinity, ease: "linear" }}
        />
        <motion.div
          className="absolute -inset-6 opacity-40 blur-md"
          style={{ background: `conic-gradient(from 180deg, transparent, ${A(0.6)}, transparent 50%, rgb(255 255 255 / 0.4) 70%, transparent)` }}
          animate={{ rotate: -360 }}
          transition={{ duration: 11, repeat: Infinity, ease: "linear" }}
        />
        {/* specular highlight */}
        <div className="absolute left-[22%] top-[18%] h-7 w-9 rounded-full bg-white/70 blur-md" />

        {/* sleepy face — eyes blink */}
        <div className="absolute inset-0 grid place-items-center">
          <div className="flex translate-y-1 items-center gap-3.5" style={{ filter: "drop-shadow(0 1px 2px rgb(0 0 0 / 0.4))" }}>
            <Eye delay={0} />
            <Eye delay={0.06} />
          </div>
        </div>
      </motion.div>
    </div>
  );
}
