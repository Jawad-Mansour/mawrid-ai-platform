// Feature: Dashboard widgets — To-Do, Calendar, and an embedded AI Assistant chat section.
// API:     POST /assistant/chat
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Plus, Check, Trash2, ChevronLeft, ChevronRight, CalendarDays, ListTodo, Send, Database, Lightbulb, Sparkles, ArrowRight,
} from "lucide-react";
import { apiPost, apiErr } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Spinner } from "@/components/ui";
import { Markdown } from "@/components/Markdown";

const uid = () => (crypto?.randomUUID?.() ?? String(Date.now() + Math.random()));

// ── To-Do ────────────────────────────────────────────────────────────────────
interface Todo { id: string; text: string; done: boolean }
const TKEY = "mawrid_todos";

export function TodoWidget() {
  const [todos, setTodos] = useState<Todo[]>(() => { try { return JSON.parse(localStorage.getItem(TKEY) || "[]") as Todo[]; } catch { return []; } });
  const [text, setText] = useState("");
  useEffect(() => { localStorage.setItem(TKEY, JSON.stringify(todos)); }, [todos]);
  const add = () => { const t = text.trim(); if (!t) return; setTodos((x) => [{ id: uid(), text: t, done: false }, ...x]); setText(""); };
  const done = todos.filter((t) => t.done).length;

  return (
    <div className="flex h-full flex-col">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-700 text-ink"><ListTodo className="h-4 w-4 text-gold-soft" /> To-do</h3>
        <span className="text-xs text-ink-faint">{done}/{todos.length} done</span>
      </div>
      <form onSubmit={(e) => { e.preventDefault(); add(); }} className="mb-3 flex gap-2">
        <input className="input !py-2 text-sm" placeholder="Add a task…" value={text} onChange={(e) => setText(e.target.value)} />
        <button type="submit" className="btn-gold !px-3 !py-2"><Plus className="h-4 w-4" /></button>
      </form>
      <div className="-mr-1 flex-1 space-y-1.5 overflow-y-auto pr-1">
        {todos.length === 0 && <p className="py-6 text-center text-xs text-ink-faint">Nothing yet — add your first task.</p>}
        {todos.map((t) => (
          <motion.div key={t.id} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} className="group flex items-center gap-2 rounded-lg border border-line bg-white/[0.02] px-2.5 py-2">
            <button onClick={() => setTodos((x) => x.map((y) => (y.id === t.id ? { ...y, done: !y.done } : y)))}
              className={cn("grid h-4 w-4 shrink-0 place-items-center rounded border", t.done ? "border-emerald bg-emerald text-bg" : "border-line")}>
              {t.done && <Check className="h-3 w-3" />}
            </button>
            <span className={cn("flex-1 truncate text-xs", t.done ? "text-ink-faint line-through" : "text-ink")}>{t.text}</span>
            <button onClick={() => setTodos((x) => x.filter((y) => y.id !== t.id))} className="shrink-0 text-ink-faint opacity-0 transition-opacity hover:text-danger group-hover:opacity-100"><Trash2 className="h-3.5 w-3.5" /></button>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

// ── Calendar ─────────────────────────────────────────────────────────────────
export interface CalEvent { date: string; label: string; tone?: "gold" | "emerald" | "danger" | "grape" }
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const iso = (y: number, m: number, d: number) => `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
const toneBg: Record<string, string> = { gold: "bg-gold", emerald: "bg-emerald", danger: "bg-danger", grape: "bg-grape" };

export function CalendarWidget({ events = [] }: { events?: CalEvent[] }) {
  const today = new Date();
  const [cur, setCur] = useState({ y: today.getFullYear(), m: today.getMonth() });
  const first = new Date(cur.y, cur.m, 1).getDay();
  const days = new Date(cur.y, cur.m + 1, 0).getDate();
  const byDate = events.reduce<Record<string, CalEvent[]>>((acc, e) => { (acc[e.date] ||= []).push(e); return acc; }, {});
  const shift = (n: number) => setCur(({ y, m }) => { const d = new Date(y, m + n, 1); return { y: d.getFullYear(), m: d.getMonth() }; });
  const upcoming = events.filter((e) => e.date >= iso(today.getFullYear(), today.getMonth(), today.getDate())).sort((a, b) => a.date.localeCompare(b.date)).slice(0, 3);

  return (
    <div className="flex h-full flex-col">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-700 text-ink"><CalendarDays className="h-4 w-4 text-gold-soft" /> {MONTHS[cur.m]} {cur.y}</h3>
        <div className="flex gap-1">
          <button onClick={() => shift(-1)} className="grid h-6 w-6 place-items-center rounded-md border border-line text-ink-soft hover:bg-white/[0.05]"><ChevronLeft className="h-3.5 w-3.5" /></button>
          <button onClick={() => shift(1)} className="grid h-6 w-6 place-items-center rounded-md border border-line text-ink-soft hover:bg-white/[0.05]"><ChevronRight className="h-3.5 w-3.5" /></button>
        </div>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center text-[10px] text-ink-faint">
        {["S", "M", "T", "W", "T", "F", "S"].map((d, i) => <div key={i}>{d}</div>)}
      </div>
      <div className="mt-1 grid grid-cols-7 gap-1">
        {Array.from({ length: first }).map((_, i) => <div key={`e${i}`} />)}
        {Array.from({ length: days }).map((_, i) => {
          const d = i + 1;
          const key = iso(cur.y, cur.m, d);
          const isToday = cur.y === today.getFullYear() && cur.m === today.getMonth() && d === today.getDate();
          const evs = byDate[key] ?? [];
          return (
            <div key={d} title={evs.map((e) => e.label).join(", ")}
              className={cn("relative grid aspect-square place-items-center rounded-md text-[11px]", isToday ? "bg-gold/20 font-800 text-gold-soft ring-1 ring-gold/40" : "text-ink-soft hover:bg-white/[0.04]")}>
              {d}
              {evs.length > 0 && (
                <div className="absolute bottom-0.5 flex gap-0.5">
                  {evs.slice(0, 3).map((e, j) => <span key={j} className={cn("h-1 w-1 rounded-full", toneBg[e.tone ?? "gold"])} />)}
                </div>
              )}
            </div>
          );
        })}
      </div>
      {upcoming.length > 0 && (
        <div className="mt-3 space-y-1 border-t border-line pt-2">
          {upcoming.map((e, i) => (
            <div key={i} className="flex items-center gap-2 text-[11px] text-ink-soft">
              <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", toneBg[e.tone ?? "gold"])} />
              <span className="font-mono text-ink-faint">{e.date.slice(5)}</span>
              <span className="truncate">{e.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Embedded AI Assistant ─────────────────────────────────────────────────────
type Role = "advisor" | "command_center";
interface Msg { who: "user" | "bot"; text: string }

export function DashboardChat() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [role, setRole] = useState<Role>("command_center");
  const [busy, setBusy] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  useEffect(() => { listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" }); }, [msgs, busy]);

  async function send(text: string) {
    const t = text.trim();
    if (!t || busy) return;
    setMsgs((m) => [...m, { who: "user", text: t }]);
    setQ(""); setBusy(true);
    try {
      const history = msgs.slice(-6).map((m) => ({ role: m.who === "user" ? "user" : "assistant", content: m.text }));
      const r = await apiPost<{ answer: string }>("/assistant/chat", { role, message: t, history, lang: "en" });
      setMsgs((m) => [...m, { who: "bot", text: r.answer }]);
    } catch (e) {
      setMsgs((m) => [...m, { who: "bot", text: apiErr(e, "I couldn't reach the assistant.") }]);
    } finally { setBusy(false); }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-700 text-ink"><Sparkles className="h-4 w-4 text-gold-soft" /> AI Assistant</h3>
        <Link to="/intelligence" className="flex items-center gap-1 text-xs font-600 text-gold-soft hover:underline">Open full <ArrowRight className="h-3 w-3" /></Link>
      </div>
      <div className="mb-2 flex gap-1 rounded-xl border border-line bg-white/[0.02] p-0.5 text-xs">
        {([["advisor", "Advisor", Lightbulb], ["command_center", "Command Center", Database]] as const).map(([k, label, Icon]) => (
          <button key={k} onClick={() => setRole(k)} className={cn("flex flex-1 items-center justify-center gap-1.5 rounded-lg py-1.5 font-600 transition-all", role === k ? "bg-gold/15 text-gold-soft" : "text-ink-soft hover:text-ink")}>
            <Icon className="h-3.5 w-3.5" /> {label}
          </button>
        ))}
      </div>
      <div ref={listRef} className="-mr-1 flex-1 space-y-2 overflow-y-auto pr-1">
        {msgs.length === 0 && (
          <div className="space-y-1.5 py-2">
            {(role === "command_center"
              ? ["How many products in stock?", "What's awaiting approval?", "Any shipments arriving soon?"]
              : ["How can I improve cash flow?", "What should I focus on this week?"]
            ).map((s) => (
              <button key={s} onClick={() => send(s)} className="block w-full truncate rounded-lg border border-line bg-white/[0.02] px-2.5 py-1.5 text-left text-[11px] text-ink-soft hover:border-gold/40 hover:text-ink">{s}</button>
            ))}
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={cn("flex", m.who === "user" && "justify-end")}>
            <div className={cn("max-w-[85%] rounded-xl px-3 py-1.5 text-xs", m.who === "user" ? "bg-gold/15 text-ink" : "border border-line bg-bg-soft text-ink-soft")}>
              {m.who === "user" ? m.text : <Markdown>{m.text}</Markdown>}
            </div>
          </div>
        ))}
        {busy && <div className="flex items-center gap-2 text-xs text-ink-soft"><Spinner className="h-3.5 w-3.5" /> Thinking…</div>}
      </div>
      <form onSubmit={(e) => { e.preventDefault(); send(q); }} className="mt-2 flex gap-2">
        <input className="input !py-2 text-sm" placeholder={role === "advisor" ? "Ask for advice…" : "Ask about your data…"} value={q} onChange={(e) => setQ(e.target.value)} />
        <button type="submit" disabled={busy || !q.trim()} className="btn-gold !px-3 !py-2">{busy ? <Spinner className="h-4 w-4" /> : <Send className="h-4 w-4" />}</button>
      </form>
    </div>
  );
}
