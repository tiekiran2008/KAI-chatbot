import React from 'react';
import { Bot, BookOpen, FileText } from 'lucide-react';
import dynamic from 'next/dynamic';

const Markdown = dynamic(() => import('@/components/Markdown'), { ssr: false });

export default function ChatMessage({ msg, documents, onSelectDocument }) {
  const isUser = msg.role === 'user';
  const ts = msg.created_at
    ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '';

  if (isUser) {
    return (
      <div className="w-full">
        <div className="flex justify-end w-full chat-msg-enter">
          <div className="flex flex-col items-end max-w-[85%] sm:max-w-[70%] gap-1">
            <div className="px-4 py-2.5 bg-primary/20 border border-primary/30 text-primary-foreground rounded-2xl rounded-tr-sm text-[14px] leading-relaxed shadow-sm break-words whitespace-pre-wrap select-text">
              {msg.content}
            </div>
            {ts && <span className="text-[9px] text-gray-500 px-1 select-none">{ts}</span>}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full">
      <div className="flex gap-4 w-full chat-msg-enter items-start pt-1 pb-3">
        <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center bg-card border border-border shadow-sm select-none overflow-hidden">
          <img src="/logo.png" alt="AI" className="w-5 h-5 logo-animate" />
        </div>
        <div className="flex-1 min-w-0 flex flex-col gap-2">
          <div className="text-[14px] text-gray-200 leading-relaxed break-words select-text">
            <Markdown content={msg.content} />
          </div>

          {/* RAG Citations (AI only) */}
          {msg.citations && msg.citations.length > 0 && (
            <div className="mt-2 pt-3 border-t border-white/[0.05] space-y-2 select-none">
              <p className="text-[9px] font-bold text-gray-500 uppercase tracking-wide flex items-center gap-1">
                <BookOpen size={9} className="text-primary" />
                Sources ({msg.citations.length})
              </p>
              <div className="flex flex-wrap gap-1.5">
                {msg.citations.map((cit, ci) => (
                  <button
                    key={ci}
                    onClick={() => {
                      const d = documents?.find((x) => x.filename === cit.filename);
                      if (d && onSelectDocument) onSelectDocument(d.id, d.filename);
                    }}
                    className="px-2 py-0.5 bg-primary/10 hover:bg-primary/20 border border-primary/20 rounded text-[9px] text-primary font-medium transition-colors"
                    title={`${(cit.score * 100).toFixed(1)}% match`}
                  >
                    <FileText size={9} className="inline mr-1 opacity-70" />
                    {cit.filename} · p.{cit.page_numbers}
                  </button>
                ))}
              </div>
              <div className="space-y-1">
                {msg.citations.map((cit, ci) => cit.text && (
                  <details key={ci} className="group border border-white/[0.06] rounded-xl overflow-hidden">
                    <summary className="px-3 py-1.5 text-[9px] text-gray-400 cursor-pointer flex justify-between items-center hover:bg-white/[0.03] select-none list-none">
                      <span className="truncate max-w-[200px]">{cit.filename} (p.{cit.page_numbers})</span>
                      <span className="text-primary text-[9px] ml-2 flex-shrink-0">{(cit.score * 100).toFixed(1)}%</span>
                    </summary>
                    <div className="px-3 py-2 text-[9px] text-gray-400 font-mono whitespace-pre-wrap bg-black/20 border-t border-white/[0.06] leading-relaxed">
                      {cit.text}
                    </div>
                  </details>
                ))}
              </div>
            </div>
          )}
          {ts && <span className="text-[9px] text-gray-500 select-none">{ts}</span>}
        </div>
      </div>
    </div>
  );
}
