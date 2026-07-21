import React, { useState, useRef } from 'react';
import { 
  X, User as UserIcon, MessageSquare, Palette, Volume2, 
  Database, Shield, UploadCloud, LogOut, Check
} from 'lucide-react';
import { useSettings } from '@/context/SettingsContext';
import { API_BASE_URL } from '@/lib/config';

const SettingsModal = ({ isOpen, onClose, user, onLogout }) => {
  const { settings, updateSettings } = useSettings();
  const [activeTab, setActiveTab] = useState('profile');
  const [saveStatus, setSaveStatus] = useState('');
  const fileInputRef = useRef(null);

  if (!isOpen) return null;

  const handleUpdate = (key, value) => {
    updateSettings({ [key]: value });
    setSaveStatus('Saved');
    setTimeout(() => setSaveStatus(''), 2000);
  };

  const handleAvatarUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onloadend = async () => {
      const base64 = reader.result;
      const token = localStorage.getItem("token");
      if (token) {
        try {
          await fetch(`${API_BASE_URL}/api/v1/users/avatar`, {
            method: "POST",
            headers: { 
              "Authorization": `Bearer ${token}`,
              "Content-Type": "application/json"
            },
            body: JSON.stringify({ avatar_base64: base64 })
          });
          // Update local UI immediately (we could store avatar in settings context too)
          // For now, let's just alert success
          setSaveStatus('Avatar uploaded! Please refresh.');
          setTimeout(() => setSaveStatus(''), 3000);
        } catch (err) {
          console.error(err);
        }
      }
    };
    reader.readAsDataURL(file);
  };

  const tabs = [
    { id: 'profile', icon: UserIcon, label: 'User Profile' },
    { id: 'chat', icon: MessageSquare, label: 'Chat Settings' },
    { id: 'appearance', icon: Palette, label: 'Appearance' },
    { id: 'voice', icon: Volume2, label: 'Voice' },
    { id: 'memory', icon: Database, label: 'Memory' },
    { id: 'privacy', icon: Shield, label: 'Privacy' },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal Container */}
      <div className="relative w-full max-w-4xl h-[80vh] flex bg-card border border-border rounded-xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        
        {/* Sidebar Navigation */}
        <div className="w-64 bg-sidebar/50 border-r border-border p-4 flex flex-col gap-2">
          <div className="px-3 pb-4 pt-2">
            <h2 className="text-xl font-semibold text-foreground">Settings</h2>
          </div>
          
          <nav className="flex-1 space-y-1">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === tab.id 
                    ? 'bg-primary/10 text-primary' 
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                }`}
              >
                <tab.icon size={18} />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Content Area */}
        <div className="flex-1 flex flex-col overflow-hidden bg-background">
          {/* Header */}
          <div className="flex items-center justify-between px-8 py-6 border-b border-border">
            <h3 className="text-lg font-medium text-foreground capitalize">
              {tabs.find(t => t.id === activeTab)?.label}
            </h3>
            
            <div className="flex items-center gap-4">
              {saveStatus && (
                <span className="flex items-center gap-1 text-sm text-green-500 animate-in fade-in">
                  <Check size={14} /> {saveStatus}
                </span>
              )}
              <button 
                onClick={onClose}
                className="p-2 rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
              >
                <X size={20} />
              </button>
            </div>
          </div>

          {/* Scrollable Content */}
          <div className="flex-1 overflow-y-auto p-8">
            <div className="max-w-2xl space-y-8">
              
              {/* --- User Profile Tab --- */}
              {activeTab === 'profile' && (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-300">
                  <div className="flex items-center gap-6">
                    <div className="w-20 h-20 rounded-full bg-muted border border-border flex items-center justify-center text-2xl font-bold text-foreground overflow-hidden">
                      {user?.avatar ? (
                        <img src={user.avatar} alt="Avatar" className="w-full h-full object-cover" />
                      ) : (
                        user?.full_name?.[0]?.toUpperCase() || 'U'
                      )}
                    </div>
                    <div>
                      <input 
                        type="file" 
                        ref={fileInputRef} 
                        onChange={handleAvatarUpload} 
                        accept="image/*" 
                        className="hidden" 
                      />
                      <button 
                        onClick={() => fileInputRef.current?.click()}
                        className="px-4 py-2 bg-secondary hover:bg-secondary/80 text-secondary-foreground rounded-lg text-sm font-medium transition-colors"
                      >
                        Upload Picture
                      </button>
                    </div>
                  </div>
                  
                  <div className="space-y-4">
                    <div className="grid gap-1.5">
                      <label className="text-sm font-medium text-foreground">Display Name</label>
                      <input 
                        type="text" 
                        defaultValue={user?.full_name} 
                        disabled
                        className="px-3 py-2 bg-muted/50 border border-border rounded-lg text-sm opacity-70 cursor-not-allowed"
                      />
                    </div>
                    <div className="grid gap-1.5">
                      <label className="text-sm font-medium text-foreground">Email</label>
                      <input 
                        type="text" 
                        defaultValue={user?.email} 
                        disabled
                        className="px-3 py-2 bg-muted/50 border border-border rounded-lg text-sm opacity-70 cursor-not-allowed"
                      />
                    </div>
                  </div>

                  <div className="pt-6 border-t border-border">
                    <button 
                      onClick={onLogout}
                      className="flex items-center gap-2 text-red-500 hover:text-red-400 font-medium transition-colors"
                    >
                      <LogOut size={16} />
                      Log out of all devices
                    </button>
                  </div>
                </div>
              )}

              {/* --- Chat Settings Tab --- */}
              {activeTab === 'chat' && (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-300">
                  <div className="grid gap-1.5">
                    <label className="text-sm font-medium text-foreground">AI Model</label>
                    <select 
                      value={settings.ai_model || "gemini-2.5-flash"} 
                      onChange={(e) => handleUpdate("ai_model", e.target.value)}
                      className="px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground focus:ring-2 focus:ring-primary outline-none"
                    >
                      <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
                      <option value="gemini-2.5-pro">Gemini 2.5 Pro</option>
                    </select>
                  </div>

                  <div className="grid gap-3">
                    <div className="flex justify-between">
                      <label className="text-sm font-medium text-foreground">Temperature ({settings.temperature})</label>
                      <span className="text-xs text-muted-foreground">Creativity vs Precision</span>
                    </div>
                    <input 
                      type="range" 
                      min="0" max="2" step="0.1" 
                      value={settings.temperature} 
                      onChange={(e) => handleUpdate("temperature", parseFloat(e.target.value))}
                      className="w-full accent-primary"
                    />
                  </div>

                  <div className="grid gap-1.5">
                    <label className="text-sm font-medium text-foreground">Max Tokens</label>
                    <input 
                      type="number" 
                      value={settings.max_tokens} 
                      onChange={(e) => handleUpdate("max_tokens", parseInt(e.target.value))}
                      className="px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground"
                    />
                  </div>

                  <div className="grid gap-1.5 pt-4">
                    <label className="text-sm font-medium text-foreground">Custom Instructions (System Prompt)</label>
                    <p className="text-xs text-muted-foreground mb-2">What would you like the AI to know about you to provide better responses?</p>
                    <textarea 
                      rows={5}
                      value={settings.system_prompt || ""}
                      onChange={(e) => handleUpdate("system_prompt", e.target.value)}
                      placeholder="E.g. I am a software engineer. Always provide answers in Python..."
                      className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground focus:ring-2 focus:ring-primary outline-none resize-none"
                    />
                  </div>
                </div>
              )}

              {/* --- Appearance Tab --- */}
              {activeTab === 'appearance' && (
                <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-300">
                  <div className="space-y-3">
                    <label className="text-sm font-medium text-foreground">Theme</label>
                    <div className="grid grid-cols-3 gap-3">
                      {['light', 'dark', 'system'].map((t) => (
                        <button
                          key={t}
                          onClick={() => handleUpdate("theme", t)}
                          className={`px-4 py-3 border rounded-xl flex items-center justify-center capitalize font-medium transition-all ${
                            settings.theme === t 
                              ? 'border-primary bg-primary/10 text-primary' 
                              : 'border-border bg-card text-muted-foreground hover:bg-muted'
                          }`}
                        >
                          {t}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-3">
                    <label className="text-sm font-medium text-foreground">Accent Color</label>
                    <div className="flex gap-3">
                      {['#1d4ed8', '#10b981', '#f43f5e', '#8b5cf6', '#f59e0b'].map((color) => (
                        <button
                          key={color}
                          onClick={() => handleUpdate("accent_color", color)}
                          className={`w-8 h-8 rounded-full transition-all flex items-center justify-center ${settings.accent_color === color ? 'ring-2 ring-offset-2 ring-offset-background ring-foreground scale-110' : 'hover:scale-110'}`}
                          style={{ backgroundColor: color }}
                        >
                          {settings.accent_color === color && <Check size={14} className="text-white" />}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* --- Voice Tab --- */}
              {activeTab === 'voice' && (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-300">
                  <div className="flex items-center justify-between p-4 border border-border rounded-xl bg-card">
                    <div>
                      <h4 className="font-medium text-foreground">Voice Input</h4>
                      <p className="text-xs text-muted-foreground">Allow microphone access for voice dictation</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input 
                        type="checkbox" 
                        className="sr-only peer" 
                        checked={settings.voice_input}
                        onChange={(e) => handleUpdate("voice_input", e.target.checked)}
                      />
                      <div className="w-11 h-6 bg-muted peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
                    </label>
                  </div>
                  
                  <div className="flex items-center justify-between p-4 border border-border rounded-xl bg-card">
                    <div>
                      <h4 className="font-medium text-foreground">Voice Output</h4>
                      <p className="text-xs text-muted-foreground">Automatically speak AI responses</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input 
                        type="checkbox" 
                        className="sr-only peer" 
                        checked={settings.voice_output}
                        onChange={(e) => handleUpdate("voice_output", e.target.checked)}
                      />
                      <div className="w-11 h-6 bg-muted peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
                    </label>
                  </div>
                </div>
              )}

              {/* --- Memory Tab --- */}
              {activeTab === 'memory' && (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-300">
                  <div className="flex items-center justify-between p-4 border border-border rounded-xl bg-card">
                    <div>
                      <h4 className="font-medium text-foreground">Long-term Memory (RAG)</h4>
                      <p className="text-xs text-muted-foreground">Allow AI to remember details across all chats</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input 
                        type="checkbox" 
                        className="sr-only peer" 
                        checked={settings.memory_enabled}
                        onChange={(e) => handleUpdate("memory_enabled", e.target.checked)}
                      />
                      <div className="w-11 h-6 bg-muted peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
                    </label>
                  </div>
                </div>
              )}

              {/* --- Privacy Tab --- */}
              {activeTab === 'privacy' && (
                <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-300">
                  <div className="space-y-4">
                    <button className="w-full flex items-center justify-between px-4 py-3 bg-card border border-border rounded-xl hover:bg-muted transition-colors text-sm font-medium">
                      <span>Export all chat data</span>
                      <UploadCloud size={16} className="text-muted-foreground" />
                    </button>
                    
                    <button className="w-full flex items-center justify-between px-4 py-3 bg-red-500/10 border border-red-500/20 text-red-500 rounded-xl hover:bg-red-500/20 transition-colors text-sm font-medium">
                      <span>Clear all chat history</span>
                      <Trash2Icon />
                    </button>
                    
                    <button className="w-full flex items-center justify-between px-4 py-3 bg-red-500/10 border border-red-500/20 text-red-500 rounded-xl hover:bg-red-500/20 transition-colors text-sm font-medium">
                      <span>Delete account completely</span>
                      <Shield size={16} />
                    </button>
                  </div>
                </div>
              )}
              
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const Trash2Icon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
);

export default SettingsModal;
