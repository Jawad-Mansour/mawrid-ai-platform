// Feature: AI Chatbot — floating RAG assistant (admin scope)
import { useEffect, useRef, useState } from "react";
import { MessageCircle, X, Send, Sparkles } from "lucide-react";
import { apiPost, apiErr } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Spinner } from "@/components/ui";

interface Msg {
  role: "user" | "bot";
  text: string;
  meta?: { route?: string | null; intent?: string | null; sources?: number };
}

export function Chatbot() {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([
    { role: "bot", text: "Hi — I'm your catalog assistant. Ask me about products, stock, suppliers, or orders." },
  ]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const sessionId = useRef(crypto.randomUUID());
  const listRef = useRef<HTMLDivElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  // Click outside the widget (or Escape) minimizes it.
  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  async function send() {
    const query = q.trim();
    if (!query || busy) return;
    setMsgs((m) => [...m, { role: "user", text: query }]);
    setQ("");
    setBusy(true);
    try {
      const r = await apiPost<{ answer: string }>("/assistant/chat", { role: "command_center", message: query, lang: "en" });
      setMsgs((m) => [...m, { role: "bot", text: r.answer }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "bot", text: apiErr(e, "I couldn't reach the assistant.") }]);
    } finally {
      setBusy(false);
      requestAnimationFrame(() => listRef.current?.scrollTo({ top: 1e9, behavior: "smooth" }));
    }
  }

  return (
    <div ref={rootRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-6 right-6 z-40 grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-grape to-gold shadow-glow transition-transform hover:scale-105"
        title="AI assistant"
      >
        {open ? <X className="h-6 w-6 text-bg" /> : <MessageCircle className="h-6 w-6 text-bg" />}
      </button>

      {open && (
        <div className="glass fixed bottom-24 right-6 z-40 flex h-[560px] w-[380px] max-w-[calc(100vw-3rem)] flex-col overflow-hidden rounded-2xl">
          <div className="flex items-center gap-2 border-b border-line bg-grape/10 px-4 py-3">
            <Sparkles className="h-4 w-4 text-grape-soft" />
            <span className="font-700 text-ink">Catalog Assistant</span>
            <span className="ml-auto chip border-grape/40 bg-grape/15 text-grape-soft">RAG</span>
          </div>

          <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto p-4">
            {msgs.map((m, i) => (
              <div key={i} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
                <div
                  className={cn(
                    "max-w-[85%] whitespace-pre-wrap rounded-2xl px-3.5 py-2.5 text-sm",
                    m.role === "user" ? "bg-gold text-bg" : "border border-line bg-white/[0.03] text-ink",
                  )}
                >
                  {m.text}
                  {m.meta && (m.meta.route || m.meta.sources != null) && (
                    <div className="mt-1.5 flex gap-1.5 text-[10px] text-ink-faint">
                      {m.meta.route && <span className="chip border-line bg-black/20">{m.meta.route}</span>}
                      {m.meta.sources != null && <span className="chip border-line bg-black/20">{m.meta.sources} sources</span>}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {busy && <div className="flex items-center gap-2 text-ink-soft"><Spinner className="h-4 w-4" /> thinking…</div>}
          </div>

          <form
            onSubmit={(e) => { e.preventDefault(); send(); }}
            className="flex items-center gap-2 border-t border-line p-3"
          >
            <input className="input" placeholder="Ask about your catalog…" value={q} onChange={(e) => setQ(e.target.value)} />
            <button type="submit" disabled={busy} className="btn-gold !px-3"><Send className="h-4 w-4" /></button>
          </form>
        </div>
      )}
    </div>
  );
}
