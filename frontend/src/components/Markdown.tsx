// Feature: Catalog — themed Markdown renderer for rich AI-overview product descriptions
import ReactMarkdown from "react-markdown";

export function Markdown({ children, className = "" }: { children: string; className?: string }) {
  return (
    <div className={`mk text-sm leading-relaxed text-ink-soft ${className}`}>
      <ReactMarkdown
        components={{
          h1: (p) => <h3 className="mb-1 mt-4 text-base font-700 text-ink" {...p} />,
          h2: (p) => <h4 className="mb-1.5 mt-4 text-sm font-700 uppercase tracking-wide text-gold-soft" {...p} />,
          h3: (p) => <h5 className="mb-1 mt-3 text-sm font-600 text-ink" {...p} />,
          p: (p) => <p className="mb-2" {...p} />,
          ul: (p) => <ul className="mb-3 space-y-1" {...p} />,
          li: (p) => (
            <li className="flex gap-2">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-gold/70" />
              <span {...p} />
            </li>
          ),
          strong: (p) => <strong className="font-700 text-ink" {...p} />,
          a: (p) => <a className="text-gold-soft underline decoration-gold/40 hover:decoration-gold" target="_blank" rel="noreferrer" {...p} />,
          code: (p) => <code className="rounded bg-black/30 px-1 py-0.5 font-mono text-xs text-ink" {...p} />,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
