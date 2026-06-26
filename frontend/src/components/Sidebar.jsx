import React, { useState } from 'react';
import { 
  MessageSquare, Plus, FileText, Trash2, LogOut, UploadCloud, 
  Settings, User, ChevronLeft, Menu, Loader2, Edit2, Check, X, ChevronDown
} from 'lucide-react';

const Sidebar = React.memo(function Sidebar({
  chats,
  selectedChatId,
  onSelectChat,
  onNewChat,
  onDeleteChat,
  onRenameChat, // Pass renaming action from parent page
  documents,
  onDeleteDocument,
  onSelectDocument,
  onOpenUpload,
  user,
  onLogout
}) {
  const [isOpen, setIsOpen] = useState(true);
  const [deletingChatId, setDeletingChatId] = useState(null);
  const [deletingDocId, setDeletingDocId] = useState(null);
  
  // Inline Renaming State
  const [editingChatId, setEditingChatId] = useState(null);
  const [renameValue, setRenameValue] = useState("");
  const [isRenamingLoading, setIsRenamingLoading] = useState(false);

  const handleDeleteChatClick = async (e, chatId) => {
    e.stopPropagation();
    setDeletingChatId(chatId);
    try {
      await onDeleteChat(chatId);
    } finally {
      setDeletingChatId(null);
    }
  };

  const handleDeleteDocClick = async (e, docId) => {
    e.stopPropagation();
    setDeletingDocId(docId);
    try {
      await onDeleteDocument(docId);
    } finally {
      setDeletingDocId(null);
    }
  };

  const handleSaveRename = async (chatId) => {
    const cleanTitle = renameValue.trim();
    if (!cleanTitle || cleanTitle === chats.find(c => c.id === chatId)?.title) {
      setEditingChatId(null);
      return;
    }
    
    setIsRenamingLoading(true);
    try {
      await onRenameChat(chatId, cleanTitle);
    } catch (err) {
      console.error("Failed to rename chat:", err);
    } finally {
      setIsRenamingLoading(false);
      setEditingChatId(null);
    }
  };

  return (
    <>
      {/* Mobile Toggle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="lg:hidden fixed top-3 left-3 z-50 p-2 bg-card border border-border rounded-lg text-foreground hover:bg-border/30 transition-all shadow-md"
      >
        <Menu size={18} />
      </button>

      {/* Primary Sidebar Container */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-[260px] bg-sidebar border-r border-sidebar-border flex flex-col transition-transform duration-300 ease-in-out lg:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        
        {/* Top Header & New Chat button */}
        <div className="p-3.5 space-y-3">
          <div className="flex items-center gap-3 px-1 py-1 select-none">
            <img src="/logo.png" alt="KAI Logo" className="w-8 h-8 logo-animate" />
            <span className="text-xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-blue-500 to-purple-500">
              KAI
            </span>
          </div>

          <div className="pb-1">
            <div className="flex items-center justify-between hover:bg-card/50 px-3 py-2.5 rounded-xl transition-all cursor-pointer border border-border/30 w-full group">
              <span className="text-sm font-semibold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-blue-500 to-purple-500 drop-shadow-sm">KAI 1.5 Flash</span>
              <ChevronDown size={14} className="text-gray-400 group-hover:text-primary transition-colors" />
            </div>
          </div>

          <button
            onClick={() => {
              onNewChat();
              if (window.innerWidth < 1024) setIsOpen(false);
            }}
            className="w-full h-10 px-3 flex items-center gap-2 bg-transparent hover:bg-primary/10 hover:border-primary/30 border border-border rounded-lg text-foreground hover:text-primary text-xs font-semibold transition-all shadow-sm group"
          >
            <Plus size={14} className="text-foreground group-hover:text-primary transition-colors" />
            <span>New Chat</span>
          </button>
        </div>

        {/* Chats History Section */}
        <div className="flex-1 overflow-y-auto px-2 py-1 space-y-4">
          
          <div className="space-y-1">
            <div className="px-3 py-1.5 text-[10px] font-bold text-gray-500 tracking-wider uppercase select-none">
              Recent Conversations
            </div>
            
            {chats.length === 0 ? (
              <div className="px-3 py-4 text-center text-xs text-gray-500 font-medium italic select-none">
                No past sessions
              </div>
            ) : (
              <div className="space-y-0.5">
                {chats.map((chat) => {
                  const isSelected = chat.id === selectedChatId;
                  const isEditing = chat.id === editingChatId;

                  return (
                    <div
                      key={chat.id}
                      onClick={() => {
                        if (!isEditing) {
                          onSelectChat(chat.id);
                          if (window.innerWidth < 1024) setIsOpen(false);
                        }
                      }}
                      className={`group relative flex flex-col gap-1 px-3 py-2.5 rounded-lg cursor-pointer transition-all border border-transparent ${
                        isSelected 
                          ? "bg-primary/10 border-primary/20" 
                          : "hover:bg-primary/5 hover:border-primary/10"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <MessageSquare size={13} className={isSelected ? "text-primary" : "text-gray-500"} />
                        
                        {isEditing ? (
                          <div className="flex-1 flex items-center gap-1 pr-6" onClick={(e) => e.stopPropagation()}>
                            <input
                              type="text"
                              value={renameValue}
                              onChange={(e) => setRenameValue(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') handleSaveRename(chat.id);
                                if (e.key === 'Escape') setEditingChatId(null);
                              }}
                              autoFocus
                              disabled={isRenamingLoading}
                              className="flex-1 bg-background text-foreground border border-border px-1.5 py-0.5 rounded text-[11px] outline-none transition-all disabled:opacity-50"
                            />
                            <button
                              onClick={() => handleSaveRename(chat.id)}
                              disabled={isRenamingLoading}
                              className="text-foreground hover:text-foreground/80 p-0.5"
                            >
                              <Check size={11} />
                            </button>
                            <button
                              onClick={() => setEditingChatId(null)}
                              disabled={isRenamingLoading}
                              className="text-red-400 hover:text-red-300 p-0.5"
                            >
                              <X size={11} />
                            </button>
                          </div>
                        ) : (
                          <>
                            <span className={`text-[12px] font-semibold truncate pr-12 max-w-[155px] ${isSelected ? "text-foreground" : "text-gray-300"}`} onDoubleClick={() => {
                              setEditingChatId(chat.id);
                              setRenameValue(chat.title || "New Chat");
                            }}>
                              {chat.title || "New Chat"}
                            </span>
                            
                            {/* Actions Group */}
                            <div className="absolute right-2 top-2.5 flex items-center gap-1 opacity-0 group-hover:opacity-100 bg-gradient-to-l from-sidebar via-sidebar to-transparent pl-3 transition-opacity">
                              {/* Inline Rename edit icon */}
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setEditingChatId(chat.id);
                                  setRenameValue(chat.title || "New Chat");
                                }}
                                className="hover:text-foreground text-gray-500 p-0.5 rounded transition-all"
                                title="Rename chat"
                              >
                                <Edit2 size={11} />
                              </button>

                              {/* Trash action button */}
                              <button
                                onClick={(e) => handleDeleteChatClick(e, chat.id)}
                                disabled={deletingChatId === chat.id}
                                className="hover:text-red-400 text-gray-400 p-0.5 rounded transition-all"
                                title="Delete chat"
                              >
                                {deletingChatId === chat.id ? (
                                  <Loader2 size={12} className="animate-spin text-gray-500" />
                                ) : (
                                  <Trash2 size={11} />
                                )}
                              </button>
                            </div>
                          </>
                        )}
                      </div>

                      {/* Last message preview */}
                      {!isEditing && chat.last_message && (
                        <div className="pl-5 pr-2">
                          <span className={`text-[10px] truncate block ${isSelected ? "text-gray-300" : "text-gray-500"}`}>
                            {chat.last_message}
                          </span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* RAG Documents Memory Storage section */}
          <div className="space-y-1 border-t border-sidebar-border pt-4">
            <div className="flex justify-between items-center px-3 py-1">
              <span className="text-[10px] font-bold text-gray-500 tracking-wider uppercase select-none">Knowledge Store</span>
              <button
                onClick={onOpenUpload}
                className="flex items-center gap-0.5 text-[10px] text-foreground hover:text-foreground/80 font-semibold transition-colors uppercase tracking-wider"
              >
                <UploadCloud size={10} />
                <span>Upload</span>
              </button>
            </div>

            {documents.length === 0 ? (
              <div className="px-3 py-4 text-center text-xs text-gray-500 font-medium italic select-none">
                No indexed files
              </div>
            ) : (
              <div className="space-y-0.5 max-h-[160px] overflow-y-auto">
                {documents.map((doc) => (
                  <div
                    key={doc.id}
                    onClick={() => onSelectDocument(doc.id, doc.filename)}
                    className="group relative flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] text-gray-400 hover:text-primary font-medium select-none cursor-pointer hover:bg-primary/5 transition-colors border border-transparent hover:border-primary/10"
                  >
                    <FileText size={12} className="text-gray-400 flex-shrink-0 group-hover:text-primary transition-colors" />
                    <span className="truncate pr-6 max-w-[170px] text-gray-300">{doc.filename}</span>

                    <button
                      onClick={(e) => handleDeleteDocClick(e, doc.id)}
                      disabled={deletingDocId === doc.id}
                      className="absolute right-2 opacity-0 group-hover:opacity-100 hover:text-red-400 text-gray-400 p-0.5 rounded transition-all"
                    >
                      {deletingDocId === doc.id ? (
                        <Loader2 size={11} className="animate-spin text-gray-500" />
                      ) : (
                        <Trash2 size={11} />
                      )}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

        </div>

        {/* Footer block: User details and sign out */}
        <div className="p-3 border-t border-sidebar-border bg-sidebar/50">
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2.5 px-2 py-1.5 rounded-lg hover:bg-border/20 transition-colors">
              <div className="w-8 h-8 rounded-full bg-border flex items-center justify-center text-foreground font-bold text-xs select-none">
                {user?.full_name ? user.full_name[0].toUpperCase() : user?.email ? user.email[0].toUpperCase() : 'U'}
              </div>
              <div className="flex flex-col min-w-0">
                <span className="text-xs font-semibold text-foreground truncate">{user?.full_name || 'Active User'}</span>
                <span className="text-[10px] text-gray-400 truncate">{user?.email}</span>
              </div>
            </div>

            <button
              onClick={onLogout}
              className="w-full h-8 px-2 flex items-center gap-2 hover:bg-red-500/10 border border-transparent rounded-lg text-gray-400 hover:text-red-400 text-xs font-medium transition-all"
            >
              <LogOut size={13} />
              <span>Log out</span>
            </button>
          </div>
        </div>

      </aside>

      {/* Mobile Sidebar Overlay */}
      {isOpen && (
        <div 
          onClick={() => setIsOpen(false)}
          className="lg:hidden fixed inset-0 z-30 bg-background/60 backdrop-blur-xs transition-opacity duration-300"
        />
      )}
    </>
  );
});

export default Sidebar;
