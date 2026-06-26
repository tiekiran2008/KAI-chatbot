import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/cjs/styles/prism';
import { Copy, Check } from 'lucide-react';

export default function Markdown({ content }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ node, inline, className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || '');
          const codeString = String(children).replace(/\n$/, '');
          
          return !inline ? (
            <CodeBlock language={match ? match[1] : 'text'} value={codeString} {...props} />
          ) : (
            <code className="bg-border/60 text-foreground px-1.5 py-0.5 rounded text-xs font-mono font-bold" {...props}>
              {children}
            </code>
          );
        },
        p({ children }) {
          return <p className="mb-3 last:mb-0 leading-relaxed text-foreground">{children}</p>;
        },
        ol({ children }) {
          return <ol className="list-decimal pl-5 mb-3 space-y-1.5 text-foreground">{children}</ol>;
        },
        ul({ children }) {
          return <ul className="list-disc pl-5 mb-3 space-y-1.5 text-foreground">{children}</ul>;
        },
        a({ children, href }) {
          return (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-foreground hover:text-foreground/80 hover:underline font-semibold transition-all">
              {children}
            </a>
          );
        },
        table({ children }) {
          return (
            <div className="overflow-x-auto my-4 rounded-lg border border-border select-text">
              <table className="w-full text-left border-collapse text-xs sm:text-sm">
                {children}
              </table>
            </div>
          );
        },
        thead({ children }) {
          return <thead className="bg-border/30 border-b border-border font-semibold text-foreground select-none">{children}</thead>;
        },
        tbody({ children }) {
          return <tbody className="divide-y divide-border/40 bg-card/20">{children}</tbody>;
        },
        tr({ children }) {
          return <tr className="hover:bg-border/10 transition-colors">{children}</tr>;
        },
        th({ children }) {
          return <th className="px-4 py-3 font-semibold text-foreground">{children}</th>;
        },
        td({ children }) {
          return <td className="px-4 py-3 text-foreground/80 font-normal leading-relaxed">{children}</td>;
        }
      }}
      className="text-sm prose prose-invert max-w-none break-words"
    >
      {content}
    </ReactMarkdown>
  );
}

function CodeBlock({ language, value }) {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  return (
    <div className="relative group rounded-lg overflow-hidden border border-border my-4 bg-[#1e1e1e]">
      {/* Title bar of code box */}
      <div className="flex justify-between items-center px-4 py-1.5 bg-[#252526] text-xs text-gray-400 font-mono select-none border-b border-border">
        <span>{language}</span>
        <button
          onClick={copyToClipboard}
          className="flex items-center gap-1 hover:text-gray-200 transition-colors py-0.5 px-1.5 rounded"
        >
          {copied ? (
            <>
              <Check size={12} className="text-foreground" />
              <span className="text-foreground">Copied</span>
            </>
          ) : (
            <>
              <Copy size={12} />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      
      {/* Highlighted syntax panel */}
      <div className="p-4 overflow-x-auto">
        <SyntaxHighlighter
          language={language}
          style={vscDarkPlus}
          customStyle={{
            background: 'transparent',
            padding: 0,
            margin: 0,
            fontSize: '0.85rem',
            fontFamily: 'var(--font-mono, monospace)',
          }}
        >
          {value}
        </SyntaxHighlighter>
      </div>
    </div>
  );
}
