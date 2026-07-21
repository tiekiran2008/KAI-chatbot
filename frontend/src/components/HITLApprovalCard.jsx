import React, { useState } from 'react';
import { Check, X, Edit2, Loader2, AlertTriangle } from 'lucide-react';
import dynamic from 'next/dynamic';

const Markdown = dynamic(() => import('@/components/Markdown'), { ssr: false });

const API_BASE = "https://kai-chatbot-backend.onrender.com";

export default function HITLApprovalCard({ hitlData, chatId, authHeaders, onComplete }) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editedContent, setEditedContent] = useState(hitlData.pending_action || '');
  const [error, setError] = useState(null);

  const handleAction = async (actionType) => {
    setIsSubmitting(true);
    setError(null);

    let url = `${API_BASE}/hitl/${chatId}/${actionType}`;
    let body = null;

    if (actionType === 'edit') {
      if (!editedContent.trim()) {
        setError("Edited content cannot be empty.");
        setIsSubmitting(false);
        return;
      }
      body = JSON.stringify({ edited_content: editedContent });
    }

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          ...authHeaders,
          'Content-Type': 'application/json'
        },
        body: body
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || `Failed to ${actionType} action.`);
      }

      const data = await response.json();
      // data contains: { status, chat_id, message, final_response }
      if (onComplete) {
        onComplete(data.final_response);
      }
    } catch (err) {
      setError(err.message);
      setIsSubmitting(false);
    }
  };

  return (
    <div className="w-full">
      <div className="flex gap-4 w-full chat-msg-enter items-start pt-1 pb-3">
        <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center bg-yellow-500/10 border border-yellow-500/20 text-yellow-500 shadow-sm select-none">
          <AlertTriangle size={16} />
        </div>
        
        <div className="flex-1 min-w-0 flex flex-col gap-3 max-w-2xl">
          <div className="bg-card border border-yellow-500/30 rounded-2xl p-4 shadow-sm relative overflow-hidden">
            {/* Header */}
            <div className="flex items-center gap-2 mb-3 pb-3 border-b border-white/[0.05]">
              <span className="px-2.5 py-1 bg-yellow-500/10 text-yellow-500 text-[10px] font-bold tracking-wider uppercase rounded-full border border-yellow-500/20">
                Approval Required
              </span>
              <span className="text-xs font-medium text-gray-300">
                {hitlData.pending_action_type === 'unknown' ? 'Proposed Action' : hitlData.pending_action_type}
              </span>
            </div>

            {/* Content Body */}
            {isEditing ? (
              <div className="mb-4">
                <textarea
                  className="w-full h-40 p-3 bg-black/40 border border-border rounded-lg text-[13px] text-gray-200 focus:outline-none focus:border-primary resize-none font-mono"
                  value={editedContent}
                  onChange={(e) => setEditedContent(e.target.value)}
                  disabled={isSubmitting}
                />
              </div>
            ) : (
              <div className="mb-4 text-[13px] text-gray-300 leading-relaxed bg-black/20 p-3 rounded-lg border border-white/[0.05] overflow-x-auto">
                <Markdown content={hitlData.pending_action || hitlData.message} />
              </div>
            )}

            {/* Error Message */}
            {error && (
              <div className="mb-3 p-2 bg-red-500/10 border border-red-500/20 text-red-400 text-[11px] rounded flex items-center gap-2">
                <AlertTriangle size={12} />
                {error}
              </div>
            )}

            {/* Actions */}
            <div className="flex flex-wrap items-center gap-2 mt-2">
              {isEditing ? (
                <>
                  <button
                    onClick={() => handleAction('edit')}
                    disabled={isSubmitting}
                    className="flex items-center gap-1.5 px-4 py-1.5 bg-primary/20 hover:bg-primary/30 border border-primary/30 text-primary-foreground text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
                  >
                    {isSubmitting ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                    Submit Edit
                  </button>
                  <button
                    onClick={() => setIsEditing(false)}
                    disabled={isSubmitting}
                    className="flex items-center gap-1.5 px-4 py-1.5 bg-gray-500/10 hover:bg-gray-500/20 border border-gray-500/20 text-gray-300 text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
                  >
                    Cancel
                  </button>
                </>
              ) : (
                <>
                  {hitlData.actions?.includes('approve') && (
                    <button
                      onClick={() => handleAction('approve')}
                      disabled={isSubmitting}
                      className="flex items-center gap-1.5 px-4 py-1.5 bg-green-500/20 hover:bg-green-500/30 border border-green-500/30 text-green-400 text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
                    >
                      {isSubmitting ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                      Approve
                    </button>
                  )}
                  {hitlData.actions?.includes('edit') && (
                    <button
                      onClick={() => setIsEditing(true)}
                      disabled={isSubmitting}
                      className="flex items-center gap-1.5 px-4 py-1.5 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/20 text-blue-400 text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
                    >
                      <Edit2 size={14} />
                      Edit
                    </button>
                  )}
                  {hitlData.actions?.includes('reject') && (
                    <button
                      onClick={() => handleAction('reject')}
                      disabled={isSubmitting}
                      className="flex items-center gap-1.5 px-4 py-1.5 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-red-400 text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
                    >
                      {isSubmitting ? <Loader2 size={14} className="animate-spin" /> : <X size={14} />}
                      Reject
                    </button>
                  )}
                </>
              )}
            </div>
            
          </div>
        </div>
      </div>
    </div>
  );
}
