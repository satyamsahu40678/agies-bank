import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function ChatMarkdown({ children }: { children: string }) {
  return (
    <div className="chat-markdown">
      <Markdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
          img: ({ alt }) => <span>{alt}</span>,
          table: ({ children }) => (
            <div className="chat-markdown-table" tabIndex={0} role="region" aria-label="Assistant table">
              <table>{children}</table>
            </div>
          ),
        }}
      >
        {children}
      </Markdown>
    </div>
  );
}
