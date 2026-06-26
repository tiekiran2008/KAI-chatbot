import React, { useState } from 'react';
import { BookOpen, ChevronDown, ChevronRight, FileText } from 'lucide-react';

const Citations = React.memo(function Citations({ citations }) {
  const [expanded, setExpanded] = useState({});

  if (!citations || citations.length === 0) return null;

  const toggleCitation = (index) => {
    setExpanded(prev => ({ ...prev, [index]: !prev[index] }));
  };

  return (
    <div className="mt-4 border-t border-border/50 pt-3 flex flex-col gap-2">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-400 mb-1">
        <BookOpen size={14} className="text-primary/70" />
        <span>Sources</span>
      </div>
      <div className="flex flex-col gap-2">
        {citations.map((cite, index) => {
          const isExpanded = expanded[index];
          return (
            <div key={index} className="rounded-lg border border-border/50 bg-background/30 overflow-hidden text-sm">
              <button
                onClick={() => toggleCitation(index)}
                className="w-full flex items-center justify-between p-2 hover:bg-border/30 transition-colors text-left"
              >
                <div className="flex items-center gap-2 truncate text-xs text-gray-300">
                  <FileText size={14} className="text-indigo-400" />
                  <span className="font-medium text-gray-200">{cite.filename}</span>
                  <span className="text-gray-500">•</span>
                  <span className="text-gray-400">Page {cite.page_numbers}</span>
                </div>
                {isExpanded ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronRight size={14} className="text-gray-400" />}
              </button>
              {isExpanded && (
                <div className="p-3 bg-black/20 text-xs text-gray-400 border-t border-border/50 max-h-40 overflow-y-auto leading-relaxed">
                  {cite.text}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
});

export default Citations;
