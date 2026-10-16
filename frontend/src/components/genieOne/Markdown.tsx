import ReactMarkdown, { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ExternalLink } from 'lucide-react';

/** GFM renderer for Genie answers: headings, lists, tables and links (opened in a new tab). */
const components: Components = {
  h1: ({ children }) => <h3 className="text-base font-semibold mt-2">{children}</h3>,
  h2: ({ children }) => <h3 className="text-base font-semibold mt-2">{children}</h3>,
  h3: ({ children }) => <h4 className="text-sm font-semibold mt-2">{children}</h4>,
  p: ({ children }) => <p className="leading-relaxed">{children}</p>,
  ul: ({ children }) => <ul className="list-disc pl-5 space-y-0.5">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal pl-5 space-y-0.5">{children}</ol>,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 text-lc-orange hover:underline">
      {children}
      <ExternalLink className="w-3 h-3" />
    </a>
  ),
  code: ({ children }) => <code className="px-1 rounded bg-surface-secondary text-[0.85em]">{children}</code>,
  table: ({ children }) => (
    <div className="overflow-x-auto rounded-xl border border-gray-100">
      <table className="w-full text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-surface-secondary text-text-secondary text-xs">{children}</thead>,
  th: ({ children }) => <th className="px-3 py-2 font-medium text-left whitespace-nowrap">{children}</th>,
  td: ({ children }) => <td className="px-3 py-2 whitespace-nowrap border-t border-gray-50">{children}</td>,
};

export default function Markdown({ text }: { text: string }) {
  return (
    <div className="space-y-2 text-sm">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {text}
      </ReactMarkdown>
    </div>
  );
}
