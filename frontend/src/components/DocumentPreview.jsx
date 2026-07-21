import React, { useState, useEffect } from 'react';
import { X, FileText, Search, Loader2, Calendar, HardDrive, Info } from 'lucide-react';

export default function DocumentPreview({ isOpen, docId, docName, token, onClose }) {
  const [chunks, setChunks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    if (isOpen && docId) {
      loadDocumentPreview();
    }
  }, [isOpen, docId]);

  const loadDocumentPreview = async () => {
    setLoading(true);
    setError(null);
    setChunks([]);

    try {
      const res = await fetch("https://kai-chatbot-backend.onrender.com/...", {
        headers: { "Authorization": `Bearer ${token}` }
      });

      if (!res.ok) {
        throw new Error("Failed to load document text blocks.");
      }

      const data = await res.json();
      setChunks(data);
    } catch (err) {
      console.error(err);
      setError(err.message || "Could not retrieve document preview.");
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  // Filter chunks by search query
  const filteredChunks = chunks.filter(chunk => 
    chunk.text.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Group chunks by Page Number for structured rendering
  const pagesMap = {};
  filteredChunks.forEach(chunk => {
    // page_numbers is stored as a string (e.g. "1" or "1,2")
    const pageNumStr = chunk.metadata.page_numbers || "1";
    // We grab the first primary page if it crosses boundaries
    const firstPage = pageNumStr.split(",")[0];
    
    if (!pagesMap[firstPage]) {
      pagesMap[firstPage] = [];
    }
    pagesMap[firstPage].push(chunk);
  });

  const sortedPages = Object.keys(pagesMap).sort((a, b) => parseInt(a) - parseInt(b));

  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-lg bg-card border-l border-border shadow-2xl z-50 flex flex-col animate-in slide-in-from-right duration-300">
      
      {/* Header bar */}
      <div className="p-4 border-b border-border flex justify-between items-center bg-background/50 backdrop-blur-sm select-none">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="p-2 bg-primary/10 border border-primary/20 text-primary rounded-lg">
            <FileText size={18} />
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-foreground truncate pr-2" title={docName}>{docName}</h3>
            <p className="text-[10px] text-gray-400">ChromaDB Chunk Reconstruction</p>
          </div>
        </div>
        
        <button 
          onClick={onClose}
          className="p-1 hover:bg-border/40 rounded-full transition-colors text-gray-400 hover:text-foreground"
        >
          <X size={18} />
        </button>
      </div>

      {/* Internal Search bar */}
      <div className="p-3 border-b border-border bg-sidebar/30 flex items-center select-none">
        <div className="w-full relative flex items-center">
          <Search className="absolute left-3 text-gray-500" size={14} />
          <input
            type="text"
            placeholder="Search text in document..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-8 pl-9 pr-4 rounded-lg bg-background/50 border border-border focus:border-primary/50 focus:ring-1 focus:ring-primary/20 outline-none text-xs transition-all placeholder:text-gray-500 text-gray-200"
          />
          {searchQuery && (
            <button 
              onClick={() => setSearchQuery('')}
              className="absolute right-3 text-[10px] text-gray-500 hover:text-foreground font-semibold"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Render Panel */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        
        {/* Loading spinner */}
        {loading && (
          <div className="h-full flex flex-col items-center justify-center text-center py-20 select-none">
            <Loader2 size={36} className="animate-spin text-primary mb-3" />
            <p className="text-xs text-gray-400">Loading indexed vector blocks from ChromaDB...</p>
          </div>
        )}

        {/* Error panel */}
        {error && (
          <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-200 text-xs rounded-lg flex items-start gap-2 select-none">
            <X className="text-red-400 flex-shrink-0 mt-0.5" size={14} />
            <span>{error}</span>
          </div>
        )}

        {/* Empty status */}
        {!loading && !error && chunks.length === 0 && (
          <div className="text-center py-20 text-xs text-gray-500 italic select-none">
            This document contains no readable text chunks.
          </div>
        )}

        {/* Document pages text log */}
        {!loading && !error && chunks.length > 0 && (
          <div className="space-y-6">
            
            {/* Metadata Info Panel */}
            <div className="p-3 bg-border/20 border border-border/60 rounded-xl space-y-2 select-none text-[11px] text-gray-300">
              <div className="flex justify-between items-center">
                <span className="text-gray-400 flex items-center gap-1">
                  <Info size={11} />
                  Indexed Blocks
                </span>
                <span className="font-bold text-foreground">{chunks.length} chunks</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400 flex items-center gap-1">
                  <HardDrive size={11} />
                  Spanned Range
                </span>
                <span className="font-bold text-foreground">
                  Pages 1 to {chunks[chunks.length - 1]?.metadata.page_numbers || "1"}
                </span>
              </div>
            </div>

            {/* Structured Page Content List */}
            {sortedPages.map((pageNumber) => (
              <div key={pageNumber} className="space-y-2.5">
                {/* Page number boundary header */}
                <div className="flex items-center gap-2 select-none">
                  <span className="text-[10px] font-extrabold text-primary tracking-wider uppercase bg-primary/10 border border-primary/20 px-2 py-0.5 rounded-md">
                    PAGE {pageNumber}
                  </span>
                  <div className="flex-1 h-px bg-border/50" />
                </div>

                {/* Chunks texts under page */}
                <div className="space-y-3.5 pl-1.5">
                  {pagesMap[pageNumber].map((chunk) => (
                    <div 
                      key={chunk.id} 
                      className="text-xs leading-relaxed text-gray-300 bg-border/5 border border-transparent hover:border-border/30 p-2.5 rounded-lg transition-all"
                    >
                      {chunk.text}
                    </div>
                  ))}
                </div>
              </div>
            ))}

            {searchQuery && filteredChunks.length === 0 && (
              <div className="text-center py-8 text-xs text-gray-500 select-none">
                No matching text blocks found for "{searchQuery}"
              </div>
            )}

          </div>
        )}

      </div>
    </div>
  );
}
