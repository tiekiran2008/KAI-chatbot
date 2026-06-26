import React, { useRef } from 'react';
import { Send, Paperclip, X, FileText, Square, Mic, Image } from 'lucide-react';

export default function ChatInput({
  inputMessage,
  setInputMessage,
  handleSendMessage,
  isStreaming,
  handleStopGeneration,
  attachments,
  removeAttachment,
  handleFileSelect,
  isDragging,
  onDragOver,
  onDragLeave,
  onDrop,
  glowColor
}) {
  const fileInputRef = useRef(null);

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (inputMessage.trim() || attachments.length > 0) {
        handleSendMessage(e);
        e.target.style.height = 'auto';
      }
    }
  };

  const onChange = (e) => {
    setInputMessage(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px';
  };

  return (
    <footer 
      className="px-4 pb-6 pt-2 bg-transparent relative w-full select-none"
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      {isDragging && (
        <div className="absolute inset-0 bg-primary/15 backdrop-blur-sm border-2 border-primary border-dashed rounded-t-3xl z-20 flex items-center justify-center">
          <div className="bg-background/90 px-6 py-3 rounded-2xl flex items-center gap-2 shadow-2xl animate-in zoom-in duration-200">
            <Paperclip className="text-primary animate-bounce" size={20} />
            <span className="text-sm font-semibold text-primary">Drop files to attach</span>
          </div>
        </div>
      )}

      <div className="max-w-3xl mx-auto relative">
        {isStreaming && (
          <div className="absolute -top-12 left-1/2 -translate-x-1/2 z-10 animate-in slide-in-from-bottom-2 duration-300">
            <button
              onClick={handleStopGeneration}
              className="px-4 py-1.5 rounded-full bg-card/90 backdrop-blur-md border border-border text-foreground hover:text-red-400 text-xs font-semibold flex items-center gap-2 shadow-xl hover:bg-border/50 transition-all active:scale-95"
            >
              <Square size={8} className="fill-current text-red-500" />
              Stop Generation
            </button>
          </div>
        )}

        <div className="relative flex flex-col bg-card/70 backdrop-blur-xl border border-border/80 rounded-[28px] shadow-lg focus-within:border-primary/40 focus-within:ring-1 focus-within:ring-primary/20 transition-all px-2 py-1.5">
          {/* Subtle underlying glow */}
          {glowColor && (
            <div 
              className="absolute inset-0 rounded-[28px] pointer-events-none -z-10 transition-all duration-500" 
              style={{ 
                boxShadow: `0 0 30px rgba(${glowColor}, 0.15)`,
                border: `1px solid rgba(${glowColor}, 0.2)`
              }}
            />
          )}

          {/* Attachments Preview Area */}
          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-2 p-3 border-b border-border/50 mb-1">
              {attachments.map(att => (
                <div key={att.id} className="relative group flex items-center gap-2 bg-background/80 border border-border/60 rounded-xl p-1.5 pr-3 max-w-[200px]">
                  {att.previewUrl ? (
                    <div className="w-8 h-8 rounded-lg bg-black/50 overflow-hidden flex-shrink-0">
                      <img src={att.previewUrl} alt="preview" className="w-full h-full object-cover" />
                    </div>
                  ) : (
                    <div className="w-8 h-8 rounded-lg bg-foreground/10 flex items-center justify-center text-foreground flex-shrink-0">
                      <FileText size={14} />
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] text-foreground font-medium truncate">{att.file.name}</p>
                    <p className="text-[9px] text-gray-500">{(att.file.size / 1024).toFixed(1)} KB</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeAttachment(att.id)}
                    className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-gray-800 hover:bg-red-500 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all shadow-md"
                  >
                    <X size={9} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Input row */}
          <div className="flex items-center gap-1.5 px-2">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="p-2.5 text-gray-400 hover:text-foreground hover:bg-border/60 rounded-full transition-all flex-shrink-0"
              title="Upload image or file"
            >
              <Image size={18} />
            </button>
            <input 
              type="file" 
              multiple 
              className="hidden" 
              ref={fileInputRef}
              onChange={handleFileSelect}
              accept="image/*,.pdf,.doc,.docx,.txt,.csv"
            />

            <textarea
              rows={1}
              required={attachments.length === 0}
              disabled={isStreaming}
              placeholder="Enter a prompt here..."
              value={inputMessage}
              onChange={onChange}
              onKeyDown={onKeyDown}
              className="flex-1 max-h-[160px] py-2 bg-transparent text-foreground outline-none text-[15px] resize-none placeholder:text-gray-500 overflow-y-auto leading-relaxed"
              style={{ minHeight: '32px' }}
            />

            <div className="flex items-center gap-1 flex-shrink-0">
              <button
                type="button"
                className="p-2.5 text-gray-400 hover:text-foreground hover:bg-border/60 rounded-full transition-all hidden sm:flex"
                title="Use microphone"
              >
                <Mic size={18} />
              </button>

              <button
                type="button"
                onClick={(e) => {
                  if (inputMessage.trim() || attachments.length > 0) {
                    handleSendMessage(e);
                    const ta = document.querySelector('textarea');
                    if (ta) ta.style.height = 'auto';
                  }
                }}
                disabled={(!inputMessage.trim() && attachments.length === 0) || isStreaming}
                className="p-2.5 bg-primary/20 text-primary hover:bg-primary hover:text-primary-foreground rounded-full transition-all disabled:opacity-20 disabled:cursor-not-allowed disabled:bg-transparent disabled:text-gray-500 hover:scale-105 active:scale-95 flex items-center justify-center w-10 h-10"
              >
                <Send size={16} />
              </button>
            </div>
          </div>
        </div>

        <p className="text-[11px] text-gray-500/80 text-center mt-3 select-none tracking-wide">
          KAI may display inaccurate info, including about people, so double-check its responses.
        </p>
      </div>
    </footer>
  );
}

