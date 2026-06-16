// Feature: Intelligence — full-page RAG assistant (admin scope)
import { useRef, useState } from "react";
import { motion } from "framer-motion";
import { Send, Sparkles, Search, Boxes, Banknote, Truck, FileText, User } from "lucide-react";
import { apiPost, apiErr } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ChatResponse } from "@/lib/types";
import { Spinner } from "@/components/ui";

interface Msg { role: "user" | "bot"; text: string; meta?: { route?: string | null; intent?: string | null; sources?: number } }

const PROMPTS = [
  { icon: Search, title: "Find products", text: "What products do I have in stock?" },
  { icon: Banknote, title: "Overdue invoices", text: "Which invoices are overdue and how much is outstanding?" },
  { icon: Truck, title: "Shipments", text: "What's the status of my incoming shipments?" },
  { icon: FileText, title: "Suppliers", text: "Which of my suppliers has the best delivery score?" },
];

export function Intelligence() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const session = useRef(crypto.randomUUID());
  const listRef = useRef<HTMLDivElement>(null);

  async function send(text: string) {
    const query = text.trim();
    if (!query || busy) return;
    setMsgs((m) => [...m, { role: "user", text: query }]);
    setQ("");
    setBusy(true);
    requestAnimationFrame(() => listRef.current?.scrollTo({ top: 1e9, behavior: "smooth" }));
    try {
      const r = await apiPost<ChatResponse>("/chat/admin", { query, session_id: session.current });
      setMsgs((m) => [...m, { role: "bot", text: r.answer, meta: { route: r.route, intent: r.intent, sources: r.sources?.length } }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "bot", text: apiErr(e, "I couldn't reach the assistant.") }]);
    } finally {
      setBusy(false);
      requestAnimationFrame(() => listRef.current?.scrollTo({ top: 1e9, behavior: "smooth" }));
    }
  }

  const empty = msgs.length === 0;

  return (
    <div className="flex h-[calc(100vh-9rem)] flex-col">
      {empty ? (
        <div className="flex flex-1 flex-col items-center justify-center px-4 text-center">
          <motion.div
            initial={{ scale: 0.7, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="relative mb-7 h-28 w-28"
          >
            <div className="absolute inset-0 rounded-full bg-gradient-to-br from-gold via-grape to-emerald blur-xl opacity-60 animate-float" />
            <div className="absolute inset-2 rounded-full bg-gradient-to-br from-gold to-grape shadow-glow" />
            <div className="absolute inset-0 grid place-items-center"><Sparkles className="h-9 w-9 text-bg" /></div>
          </motion.div>
          <h1 className="text-3xl font-800 tracking-tight text-ink">Welcome to Mawrid AI</h1>
          <p className="mt-2 max-w-md text-ink-soft">Ask anything about your catalog, orders, suppliers, invoices, or shipments — grounded in your real data.</p>

          <div className="mt-8 grid w-full max-w-2xl grid-cols-1 gap-3 sm:grid-cols-2">
            {PROMPTS.map((p, i) => (
              <motion.button
                key={p.title}
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.06 * i }}
                onClick={() => send(p.text)}
                className="card flex items-start gap-3 p-4 text-left transition-all hover:-translate-y-0.5 hover:shadow-glow"
              >
                <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-grape/15 text-grape-soft"><p.icon className="h-5 w-5" /></div>
                <div>
                  <div className="text-sm font-700 text-ink">{p.title}</div>
                  <div className="mt-0.5 text-xs text-ink-faint">{p.text}</div>
                </div>
              </motion.button>
            ))}
          </div>
        </div>
      ) : (
        <div ref={listRef} className="flex-1 space-y-5 overflow-y-auto px-2 py-4">
          <div className="mx-auto max-w-3xl space-y-5">
            {msgs.map((m, i) => (
              <div key={i} className={cn("flex gap-3", m.role === "user" ? "flex-row-reverse" : "")}>
                <div className={cn("grid h-9 w-9 shrink-0 place-items-center rounded-xl", m.role === "user" ? "bg-gold text-bg" : "bg-grape/20 text-grape-soft")}>
                  {m.role === "user" ? <User className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
                </div>
                <div className={cn("max-w-[80%] rounded-2xl px-4 py-3 text-sm", m.role === "user" ? "bg-gold text-bg" : "card")}>
                  <div className="whitespace-pre-wrap">{m.text}</div>
                  {m.meta && (m.meta.route || m.meta.sources != null) && (
                    <div className="mt-2 flex gap-1.5">
                      {m.meta.route && <span className="chip border-line bg-black/20 text-ink-faint">{m.meta.route}</span>}
                      {m.meta.intent && <span className="chip border-line bg-black/20 text-ink-faint">{m.meta.intent.replace(/_/g, " ")}</span>}
                      {m.meta.sources != null && <span className="chip border-line bg-black/20 text-ink-faint">{m.meta.sources} sources</span>}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {busy && <div className="flex items-center gap-2 pl-12 text-ink-soft"><Spinner className="h-4 w-4" /> thinking…</div>}
          </div>
        </div>
      )}

      {/* input */}
      <div className="mx-auto w-full max-w-3xl px-2 pb-2 pt-3">
        <form onSubmit={(e) => { e.preventDefault(); send(q); }} className="glass flex items-center gap-2 rounded-2xl p-2">
          <Boxes className="ml-2 h-5 w-5 text-ink-faint" />
          <input className="flex-1 bg-transparent px-1 py-2 text-sm text-ink outline-none placeholder:text-ink-faint" placeholder="Ask me anything about your operations…" value={q} onChange={(e) => setQ(e.target.value)} />
          <button type="submit" disabled={busy || !q.trim()} className="btn-gold !rounded-xl !px-3.5"><Send className="h-4 w-4" /></button>
        </form>
        <p className="mt-2 text-center text-xs text-ink-faint">Mawrid AI answers from your real catalog &amp; operations — always grounded, with citations.</p>
      </div>
    </div>
  );
}
