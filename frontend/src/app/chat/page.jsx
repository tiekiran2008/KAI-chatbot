"use client";

import { useRouter } from 'next/navigation';

import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, Bot, User as UserIcon, LogOut, ArrowRight, Loader2, 
  Sparkles, Shield, Mail, Lock, UserPlus, Info, Square, Compass,
  BookOpen, Code, Terminal, Clipboard, RefreshCw, AlertCircle, FileText,
  Sun, Moon, Paperclip, X, Image as ImageIcon, ChevronDown
} from 'lucide-react';

import dynamic from 'next/dynamic';

const Sidebar = dynamic(() => import('@/components/Sidebar'), { 
  ssr: false, 
  loading: () => <div className="w-[260px] h-screen bg-sidebar border-r border-sidebar-border hidden lg:block animate-pulse" />
});
const UploadModal = dynamic(() => import('@/components/UploadModal'), { ssr: false });
const DocumentPreview = dynamic(() => import('@/components/DocumentPreview'), { ssr: false });
const Markdown = dynamic(() => import('@/components/Markdown'), { ssr: false });
const ResetPasswordModal = dynamic(() => import('@/components/ResetPasswordModal'), { ssr: false });
const HITLApprovalCard = dynamic(() => import('@/components/HITLApprovalCard'), { ssr: false });
const SettingsModal = dynamic(() => import('@/components/SettingsModal'), { ssr: false });
import ChatMessage from '@/components/ChatMessage';
import ChatInput from '@/components/ChatInput';

// Import Supabase Auth client & helper
import { supabase, isSupabaseEnabled } from '@/lib/supabase';

import { API_BASE_URL as API_BASE } from '@/lib/config';

// Production-grade fetch wrapper with absolute Timeout and Abort signal handling
const fetchWithTimeout = async (url, options = {}, timeout = 12000) => {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  
  try {
    const res = await fetch(url, {
      ...options,
      signal: controller.signal
    });
    clearTimeout(timer);
    return res;
  } catch (err) {
    clearTimeout(timer);
    if (err.name === 'AbortError') {
      throw new Error("Network latency timeout: The server took too long to respond. Please ensure the backend is active.");
    }
    throw err;
  }
};

export default function ChatPage() {
  const router = useRouter();

  // --- Auth State ---
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [authMode, setAuthMode] = useState('login'); // 'login' or 'register'
  const [authForm, setAuthForm] = useState({ email: '', password: '', fullName: '' });
  const [authError, setAuthError] = useState('');
  const [authLoading, setAuthLoading] = useState(false);
  const [authReady, setAuthReady] = useState(false);

  // --- UI Modals State ---
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // --- Main App State ---
  const [chats, setChats] = useState([]);
  const [selectedChatId, setSelectedChatId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  
  // --- UI/Streaming State ---
  // Glow color is managed by GlowColorPicker component (bottom-right button)
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingBuffer, setStreamingBuffer] = useState('');
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [isResetPasswordOpen, setIsResetPasswordOpen] = useState(false);
  const [errorPanel, setErrorPanel] = useState('');

  // --- Attachments & Drag-Drop State ---
  const [attachments, setAttachments] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  // --- Stream Failure & Recovery State ---
  const [lastPrompt, setLastPrompt] = useState('');
  const [streamFailed, setStreamFailed] = useState(false);

  // --- Document Preview State ---
  const [previewDocId, setPreviewDocId] = useState(null);
  const [previewDocName, setPreviewDocName] = useState(null);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  
  const activeStreamReader = useRef(null);
  const messagesEndRef = useRef(null);

  // --- Initialize App & Check Tokens ---
  useEffect(() => {
    // 1. Supabase Session Validation & Listeners (If configured)
    if (isSupabaseEnabled()) {
      console.log("Supabase Auth Client initialized as primary auth layer.");
      
      // Get initial active session
      supabase.auth.getSession().then(({ data: { session } }) => {
        if (session) {
          setToken(session.access_token);
          // Persist token for reloads
          localStorage.setItem("token", session.access_token);
          setUser({
            email: session.user.email,
            full_name: session.user.user_metadata?.full_name || session.user.user_metadata?.name || "Supabase User"
          });
        }
        setAuthReady(true);
      });

      // Listen for dynamic auth state transitions (login, logout, token refreshes)
      const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
        if (session) {
          setToken(session.access_token);
          // Persist token for reloads
          localStorage.setItem("token", session.access_token);
          setUser({
            email: session.user.email,
            full_name: session.user.user_metadata?.full_name || session.user.user_metadata?.name || "Supabase User"
          });
        } else {
          // Clear states on signout
          setToken(null);
          setUser(null);
          setChats([]);
          setMessages([]);
          setSelectedChatId(null);
        }
      });

      return () => subscription.unsubscribe();

    } else {
      // 2. Fallback to Local Auth Session (If Supabase not active yet)
      console.log("Supabase config not found. Falling back to local relational database Auth.");
        const savedToken = localStorage.getItem("token");
        if (savedToken) {
          setToken(savedToken);
          // Pass the saved JWT token to fetchUserProfile so it can construct the correct header.
          fetchUserProfile(savedToken);
        }
        setAuthReady(true);
    }
  }, []);

  // Fetch chats and documents once authenticated
  useEffect(() => {
    if (token) {
      fetchChats();
      fetchDocuments();
    }
  }, [token]);

  // Auto Scroll to bottom
  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingBuffer, isStreaming, streamFailed]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // --- Auth Handlers ---
  // Helper to construct Authorization header and log the raw token
  const getAuthHeaders = () => {
    if (!token) {
      console.warn('[WARN] Attempted to build Authorization header with missing token');
      return {};
    }
    console.log('[DEBUG] Raw token sent in Authorization header:', token);
    return { Authorization: `Bearer ${token}` };
  };

  const fetchUserProfile = async (authToken) => {
    try {
      // Use the provided authToken directly – it should be the JWT access_token.
      // Fall back to the global token state if authToken is missing (e.g., during normal flow).
      const tokenToUse = authToken ?? token;
      console.log('[DEBUG] fetchUserProfile using token:', tokenToUse);
      const res = await fetchWithTimeout(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${tokenToUse}` }
      });
      if (res.ok) {
        const userData = await res.json();
        setUser(userData);
      } else {
        console.warn('fetchUserProfile response not OK:', res.status);
      }
    } catch (err) {
      console.error('Failed to fetch user profile:', err);
    }
  };

  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    setAuthError('');
    setAuthLoading(true);

    // Flow 1: Supabase Federated Authentication
    if (isSupabaseEnabled()) {
      try {
        if (authMode === 'register') {
          const { data, error } = await supabase.auth.signUp({
            email: authForm.email,
            password: authForm.password,
            options: {
              data: {
                full_name: authForm.fullName || "Supabase User"
              }
            }
          });

          if (error) throw error;
          
          setAuthMode('login');
          setAuthError('Registration successful! Check your email inbox to confirm registration, then sign in.');
          setAuthLoading(false);
          return;
        }

        // Login Flow
        const { data, error } = await supabase.auth.signInWithPassword({
          email: authForm.email,
          password: authForm.password
        });

        if (error) throw error;

        if (data.session) {
          setToken(data.session.access_token);
          // Persist token for page reloads / subsequent API calls
          localStorage.setItem("token", data.session.access_token);
          setUser({
            email: data.user.email,
            full_name: data.user.user_metadata?.full_name || data.user.user_metadata?.name || "Supabase User"
          });
        }

      } catch (err) {
        setAuthError(err.message || "Failed to complete Supabase Auth handshake.");
      } finally {
        setAuthLoading(false);
      }
      return;
    }

    // Flow 2: Local Database Authentication Fallback
    try {
      if (authMode === 'register') {
        const res = await fetchWithTimeout(`${API_BASE}/auth/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: authForm.fullName || "User",
            email: authForm.email,
            password: authForm.password
          })
        });

        if (!res.ok) {
          const errData = await res.json();
          throw new Error(errData.detail || "Registration failed. Account might already exist.");
        }

        setAuthMode('login');
        setAuthError('Registration successful! Please sign in.');
        setAuthLoading(false);
        return;
      }

      const formData = new URLSearchParams();
      formData.append("username", authForm.email);
      formData.append("password", authForm.password);

      // Login handler — backend expects form-data matching OAuth2PasswordRequestForm schema
      const res = await fetchWithTimeout(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formData
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Incorrect email or password.");
      }

      const data = await res.json();
      localStorage.setItem("token", data.access_token);
      setToken(data.access_token);
      fetchUserProfile(data.access_token);

    } catch (err) {
      setAuthError(err.message || "Failed to establish local database server authentication.");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = async () => {
    // Sign out from Supabase if configured
    if (isSupabaseEnabled()) {
      try {
        await supabase.auth.signOut();
      } catch (err) {
        console.error("Supabase signOut error:", err);
      }
    }
    
    // Clear storage and state regardless of provider
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
    setChats([]);
    setMessages([]);
    setSelectedChatId(null);
    setStreamFailed(false);
    setLastPrompt('');
  };

  // --- Backend Ingestion Handlers ---
  const fetchChats = async () => {
    try {
      const res = await fetchWithTimeout(`${API_BASE}/chat`, {
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const chatsList = await res.json();
        setChats(chatsList);
        // Do NOT auto-select any chat on load — user should land on a fresh empty screen.
      }
    } catch (err) {
      console.error("Failed to load chats:", err);
    }
  };

  const fetchDocuments = async () => {
    try {
      const res = await fetchWithTimeout(`${API_BASE}/documents`, {
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const docsList = await res.json();
        setDocuments(docsList);
      }
    } catch (err) {
      console.error("Failed to load documents:", err);
    }
  };

  const handleSelectChat = async (chatId) => {
    setSelectedChatId(chatId);
    setIsLoadingMessages(true);
    setErrorPanel('');
    setStreamingBuffer('');
    setIsStreaming(false);
    setStreamFailed(false);

    try {
      const res = await fetchWithTimeout(`${API_BASE}/chat/${chatId}`, {
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages || []);
        
        // Also check if there's a pending HITL action for this chat
        try {
          const hitlRes = await fetch(`${API_BASE}/hitl/${chatId}/pending`, {
            headers: getAuthHeaders()
          });
          if (hitlRes.ok) {
            const hitlData = await hitlRes.json();
            if (hitlData.status === "hitl_pending") {
              setMessages(prev => [
                ...prev,
                {
                  id: `hitl_${chatId}_${Date.now()}`,
                  chat_id: chatId,
                  role: "assistant",
                  isHitl: true,
                  hitlData: hitlData,
                  created_at: new Date().toISOString()
                }
              ]);
            }
          }
        } catch (hitlErr) {
          // Ignore, likely no pending action or HITL disabled
        }
      }
    } catch (err) {
      console.error(err);
      setErrorPanel("Failed to load conversation history. Check your database connections.");
    } finally {
      setIsLoadingMessages(false);
    }
  };

  const handleNewChat = async () => {
    setErrorPanel('');
    setMessages([]);
    setStreamingBuffer('');
    setIsStreaming(false);
    setStreamFailed(false);
    setLastPrompt('');
    
    try {
      const res = await fetchWithTimeout(`${API_BASE}/chat/`, {
        method: "POST",
        headers: {
          ...getAuthHeaders(),
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ system_prompt: "You are a professional assistant." })
      });
      if (res.ok) {
        const newChat = await res.json();
        setChats(prev => [newChat, ...prev]);
        setSelectedChatId(newChat.id);
      }
    } catch (err) {
      console.error(err);
      setErrorPanel("Failed to initialize a new conversation session.");
    }
  };

  const handleDeleteChat = async (chatId) => {
    try {
      const res = await fetchWithTimeout(`${API_BASE}/chat/${chatId}`, {
        method: "DELETE",
        headers: getAuthHeaders()
      });
      if (res.ok) {
        setChats(prev => prev.filter(c => c.id !== chatId));
        if (selectedChatId === chatId) {
          setSelectedChatId(null);
          setMessages([]);
          setStreamFailed(false);
        }
      }
    } catch (err) {
      console.error("Failed to delete chat:", err);
    }
  };

  const handleRenameChat = async (chatId, newTitle) => {
    try {
      const res = await fetchWithTimeout(`${API_BASE}/chat/${chatId}`, {
        method: "PATCH",
        headers: {
          ...getAuthHeaders(),
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ title: newTitle })
      });
      if (res.ok) {
        const updatedChat = await res.json();
        setChats(prev => prev.map(c => c.id === chatId ? { ...c, title: updatedChat.title } : c));
      } else {
        throw new Error("Failed to rename thread.");
      }
    } catch (err) {
      console.error(err);
      setErrorPanel("Failed to rename chat session.");
    }
  };

  const handleDeleteDocument = async (docId) => {
    try {
      const res = await fetchWithTimeout(`${API_BASE}/documents/${docId}`, {
        method: "DELETE",
        headers: getAuthHeaders()
      });
      if (res.ok) {
        setDocuments(prev => prev.filter(d => d.id !== docId));
        if (previewDocId === docId) {
          setIsPreviewOpen(false);
          setPreviewDocId(null);
        }
      }
    } catch (err) {
      console.error("Failed to delete document:", err);
    }
  };

  const handleSelectDocument = (docId, docName) => {
    setPreviewDocId(docId);
    setPreviewDocName(docName);
    setIsPreviewOpen(true);
  };

  // --- Real-time Streaming Execution with Recovery Loops ---
  const handleSendMessage = async (e, promptOverride = null) => {
    if (e) e.preventDefault();
    
    const userPrompt = (promptOverride || inputMessage).trim();
    if (!userPrompt || isStreaming) return;

    let chatId = selectedChatId;
    
    // 1. Initialize a new chat thread automatically if none is active
    if (!chatId) {
      try {
        const res = await fetchWithTimeout(`${API_BASE}/chat/`, {
          method: "POST",
          headers: {
            ...getAuthHeaders(),
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ system_prompt: "You are a professional assistant." })
        });
        if (res.ok) {
          const newChat = await res.json();
          setChats(prev => [newChat, ...prev]);
          chatId = newChat.id;
          setSelectedChatId(chatId);
        } else {
          throw new Error("Could not initialize thread.");
        }
      } catch (err) {
        setErrorPanel("Failed to start chat session. Ensure backend PostgreSQL is up.");
        return;
      }
    }

    // Reset recovery states
    setInputMessage('');
    setAttachments([]); // clear attachments on send
    setErrorPanel('');
    setStreamFailed(false);
    setIsStreaming(true);
    setStreamingBuffer('');
    setLastPrompt(userPrompt);

    // 2. Optimistically append user message immediately inside React logs (if not repeating retry)
    if (!promptOverride) {
      const optimisticUserMessage = {
        id: `optimistic_${Date.now()}`,
        chat_id: chatId,
        role: "user",
        content: userPrompt,
        created_at: new Date().toISOString()
      };
      setMessages(prev => [...prev, optimisticUserMessage]);
    }

    try {
      // 3. Initiate SSE POST stream fetch call with Abort Controller timeout (e.g. 15s initial wait for LLM/RAG handshakes)
      const controller = new AbortController();
      const handshakeTimer = setTimeout(() => controller.abort(), 15000);
      
      const response = await fetch(`${API_BASE}/chat/${chatId}/stream`, {
        method: "POST",
        headers: {
          ...getAuthHeaders(),
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ message: userPrompt }),
        signal: controller.signal
      });

      clearTimeout(handshakeTimer);

      if (!response.ok) {
        throw new Error("Failed to initialize response stream. Check Gemini API configurations.");
      }

      // 4. Decode the Server-Sent Events stream chunk by chunk
      const reader = response.body.getReader();
      activeStreamReader.current = reader;
      const decoder = new TextDecoder();
      
      let chunkDataBuffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        chunkDataBuffer += decoder.decode(value, { stream: true });

        const events = chunkDataBuffer.split("\n\n");
        chunkDataBuffer = events.pop();

        for (const event of events) {
          const cleanLine = event.trim();
          if (cleanLine.startsWith("data: ")) {
            const rawJsonStr = cleanLine.substring(6);
            
            try {
              const parsed = JSON.parse(rawJsonStr);
              
              if (parsed.hitl_pending) {
                const hitlMessage = {
                  id: `hitl_${parsed.chat_id}_${Date.now()}`,
                  chat_id: chatId,
                  role: "assistant",
                  isHitl: true,
                  hitlData: parsed,
                  created_at: new Date().toISOString()
                };
                
                setMessages(prev => {
                  const cleaned = prev.filter(m => !m.id.toString().startsWith("optimistic"));
                  if (cleaned.some(m => m.id === hitlMessage.id)) return prev;
                  return [
                    ...cleaned, 
                    {
                      id: `user_${parsed.chat_id}_${Date.now()}`,
                      chat_id: chatId,
                      role: "user",
                      content: userPrompt,
                      created_at: new Date().toISOString()
                    },
                    hitlMessage
                  ];
                });
                setStreamingBuffer('');
                setIsStreaming(false);
              } else if (parsed.token) {
                setStreamingBuffer(prev => prev + parsed.token);
              } else if (parsed.done) {
                const finalAssistantMessage = {
                  id: parsed.message_id,
                  chat_id: chatId,
                  role: "assistant",
                  content: parsed.content,
                  citations: parsed.citations || [],
                  created_at: new Date().toISOString()
                };
                
                setMessages(prev => {
                  const cleaned = prev.filter(m => !m.id.toString().startsWith("optimistic"));
                  if (cleaned.some(m => m.id === parsed.message_id)) return prev;
                  return [
                    ...cleaned, 
                    {
                      id: `user_${parsed.message_id}`,
                      chat_id: chatId,
                      role: "user",
                      content: userPrompt,
                      created_at: new Date().toISOString()
                    },
                    finalAssistantMessage
                  ];
                });
                setStreamingBuffer('');

                // If backend generated a new smart title, update the sidebar instantly
                if (parsed.new_title) {
                  setChats(prev => prev.map(c =>
                    c.id === chatId ? { ...c, title: parsed.new_title } : c
                  ));
                }

                fetchChats(); 
              }
            } catch (jsonErr) {
              console.warn("Could not parse chunk event:", cleanLine, jsonErr);
            }
          }
        }
      }

    } catch (err) {
      console.error(err);
      if (err.name === 'AbortError') {
        setErrorPanel("LLM Handshake Timeout: Gemini failed to respond within 15 seconds. Please retry.");
      } else {
        setErrorPanel(err.message || "Connection broken. Please ensure the backend server is active.");
      }
      
      setStreamFailed(true);
      fetchChats();
      if (chatId) {
        try {
          const syncRes = await fetchWithTimeout(`${API_BASE}/chat/${chatId}`, {
            headers: { "Authorization": `Bearer ${token}` }
          });
          if (syncRes.ok) {
            const data = await syncRes.json();
            setMessages(data.messages || []);
          }
        } catch (syncErr) {
          console.error("Failed to sync partial logs after crash:", syncErr);
        }
      }
    } finally {
      setIsStreaming(false);
      activeStreamReader.current = null;
    }
  };

  const handleHitlComplete = (finalResponse) => {
    setMessages(prev => {
      const filtered = prev.filter(m => !m.isHitl);
      return [
        ...filtered,
        {
          id: `assistant_hitl_${Date.now()}`,
          chat_id: selectedChatId,
          role: "assistant",
          content: finalResponse,
          created_at: new Date().toISOString()
        }
      ];
    });
  };

  // --- Stop Generation ---
  const handleStopGeneration = () => {
    if (activeStreamReader.current) {
      activeStreamReader.current.cancel();
      activeStreamReader.current = null;
      setIsStreaming(false);
      setStreamingBuffer('');
      if (selectedChatId) handleSelectChat(selectedChatId);
    }
  };

  // --- Attachment Handlers ---
  const uploadFileToBackend = (attachmentId, file) => {
    const formData = new FormData();
    formData.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/documents/upload`);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        const percentComplete = (event.loaded / event.total) * 100;
        const displayPercent = Math.min(percentComplete, 95); // Clamp to 95% until final indexing finishes
        setAttachments(prev => prev.map(att => 
          att.id === attachmentId ? { ...att, progress: displayPercent } : att
        ));
      }
    };

    xhr.onload = () => {
      if (xhr.status === 201) {
        try {
          const resData = JSON.parse(xhr.responseText);
          setAttachments(prev => prev.map(att => 
            att.id === attachmentId ? { ...att, status: 'success', progress: 100, dbDocId: resData.id } : att
          ));
          fetchDocuments(); // Refresh knowledge list
        } catch (err) {
          setAttachments(prev => prev.map(att => 
            att.id === attachmentId ? { ...att, status: 'error', errorMsg: 'Failed to index file' } : att
          ));
        }
      } else {
        let errorMsg = 'Upload failed';
        try {
          const resData = JSON.parse(xhr.responseText);
          errorMsg = resData.detail || errorMsg;
        } catch (e) {}
        setAttachments(prev => prev.map(att => 
          att.id === attachmentId ? { ...att, status: 'error', errorMsg } : att
        ));
      }
    };

    xhr.onerror = () => {
      setAttachments(prev => prev.map(att => 
        att.id === attachmentId ? { ...att, status: 'error', errorMsg: 'Connection error' } : att
      ));
    };

    xhr.send(formData);
  };

  const processAndUploadFiles = (files) => {
    const newAttachments = files.map(file => {
      const id = Math.random().toString(36).substr(2, 9);
      const isImage = file.type.startsWith('image/');
      const isPdf = file.type === "application/pdf" || file.name.endsWith(".pdf");
      const isValid = isPdf || isImage;
      
      const attachment = {
        id,
        file,
        previewUrl: isImage ? URL.createObjectURL(file) : null,
        status: isValid ? 'uploading' : 'error',
        progress: isValid ? 10 : 0,
        errorMsg: isValid ? null : 'Unsupported file type',
        dbDocId: null
      };

      if (isValid) {
        uploadFileToBackend(id, file);
      }

      return attachment;
    });

    setAttachments(prev => [...prev, ...newAttachments]);
  };

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files);
    if (files.length > 0) {
      processAndUploadFiles(files);
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeAttachment = async (id) => {
    const attachment = attachments.find(a => a.id === id);
    if (!attachment) return;

    if (attachment.previewUrl) {
      URL.revokeObjectURL(attachment.previewUrl);
    }

    if (attachment.dbDocId) {
      handleDeleteDocument(attachment.dbDocId);
    }

    setAttachments(prev => prev.filter(a => a.id !== id));
  };

  const onDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const onDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const onDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      processAndUploadFiles(files);
    }
  };

  // --- Auth Guard: redirect to login if not authenticated ---
  if (!token) {
    if (authReady) {
      router.push('/');
    }
    return (
      <main className="min-h-screen flex items-center justify-center bg-background text-foreground">
        <Loader2 size={32} className="animate-spin text-primary" />
      </main>
    );
  }

  // --- Main Dashboard Render ---
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-transparent">
      
      {/* Sidebar Navigation */}
      <Sidebar
        chats={chats}
        selectedChatId={selectedChatId}
        onSelectChat={handleSelectChat}
        onNewChat={handleNewChat}
        onDeleteChat={handleDeleteChat}
        onRenameChat={handleRenameChat}
        documents={documents}
        onDeleteDocument={handleDeleteDocument}
        onSelectDocument={handleSelectDocument}
        onOpenUpload={() => setIsUploadOpen(true)}
        onOpenSettings={() => setIsSettingsOpen(true)}
        user={user}
        onLogout={handleLogout}
      />

      {/* Main Dialogue Panel */}
      <main className="flex-1 flex flex-col min-w-0 pl-0 lg:pl-[260px] h-full relative">
        
        {/* Title Top Bar (Gemini Style) */}
        <header className="h-16 border-b border-border/10 flex justify-between items-center px-4 pl-14 lg:pl-6 bg-transparent backdrop-blur-[2px] z-10 select-none">
          <div className="flex items-center gap-2">
            {/* Header left area empty as model selector moved to sidebar */}
          </div>
          
          <div className="flex items-center gap-2.5 text-xs text-gray-400">
            <span className="hidden md:inline-flex bg-border/40 px-2.5 py-1 rounded-full border border-border/50 font-medium text-[10px] text-gray-300 tracking-wide">
              {isSupabaseEnabled() ? "Supabase Auth" : "RDBMS Local Auth"}
            </span>
            <div className="w-8 h-8 rounded-full bg-border/60 hover:bg-primary/20 flex items-center justify-center text-foreground font-bold text-xs select-none border border-border transition-colors cursor-pointer">
              {user?.full_name ? user.full_name[0].toUpperCase() : user?.email ? user.email[0].toUpperCase() : 'U'}
            </div>
          </div>
        </header>

         {/* Message Log Panel */}
        <div className={`${messages.length === 0 && !isLoadingMessages ? "hidden" : "flex-1"} overflow-y-auto px-4 pt-6 pb-4 scroll-smooth`} style={{scrollBehavior: 'smooth'}}>

          {/* Error banner */}
          {errorPanel && (
            <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-200 text-xs rounded-xl flex items-center justify-between gap-2 max-w-2xl mx-auto mb-4 animate-in slide-in-from-top-2 duration-300">
              <div className="flex items-center gap-2">
                <AlertCircle size={14} className="text-red-400 flex-shrink-0" />
                <span>{errorPanel}</span>
              </div>
              <button
                onClick={() => setErrorPanel('')}
                className="text-[10px] text-gray-400 hover:text-foreground underline uppercase tracking-wider flex-shrink-0"
              >
                Dismiss
              </button>
            </div>
          )}

          {/* Old Welcome Screen Removed */}

          {/* Skeleton loaders */}
          {isLoadingMessages && (
            <div className="space-y-5 max-w-3xl mx-auto pt-4">
              {[1, 2, 3].map(n => (
                <div key={n} className={`flex items-end gap-2.5 animate-pulse ${n % 2 === 0 ? 'flex-row-reverse' : ''}`}>
                  <div className="w-8 h-8 rounded-full bg-border/60 flex-shrink-0" />
                  <div className={`rounded-2xl bg-border/40 h-14 ${n % 2 === 0 ? 'w-52 rounded-br-sm' : 'w-72 rounded-bl-sm'}`} />
                </div>
              ))}
            </div>
          )}

          {/* ──────────── Message Bubbles ──────────── */}
          <div className="max-w-3xl mx-auto space-y-6 pt-2">

            {messages.map((msg) => (
              msg.isHitl ? (
                <HITLApprovalCard 
                  key={msg.id} 
                  hitlData={msg.hitlData} 
                  chatId={msg.chat_id} 
                  authHeaders={getAuthHeaders()} 
                  onComplete={handleHitlComplete} 
                />
              ) : (
                <ChatMessage 
                  key={msg.id} 
                  msg={msg} 
                  documents={documents} 
                  onSelectDocument={handleSelectDocument} 
                />
              )
            ))}

            {/* ── Live streaming bubble ── */}
            {isStreaming && streamingBuffer && (
              <div className="flex gap-4 w-full chat-msg-enter items-start pt-1 pb-3">
                <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center bg-card border border-border shadow-sm select-none overflow-hidden">
                  <img src="/logo.png" alt="AI" className="w-5 h-5 logo-animate" />
                </div>
                <div className="flex-1 min-w-0 flex flex-col gap-1">
                  <div className="text-[14px] text-foreground leading-relaxed break-words select-text">
                    <Markdown content={streamingBuffer + " ▌"} />
                  </div>
                </div>
              </div>
            )}

            {/* ── Typing dots ── */}
            {isStreaming && !streamingBuffer && (
              <div className="flex gap-4 w-full chat-msg-enter items-start pt-1 pb-3">
                <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center bg-card border border-border shadow-sm select-none overflow-hidden">
                  <img src="/logo.png" alt="AI" className="w-5 h-5 logo-animate" />
                </div>
                <div className="flex-1 min-w-0 flex flex-col gap-1">
                  <div className="inline-flex px-4 py-2 bg-card border border-border rounded-2xl rounded-tl-sm shadow-sm items-center gap-1.5 w-max">
                    <span className="w-1.5 h-1.5 bg-gray-500 rounded-full typing-dot" />
                    <span className="w-1.5 h-1.5 bg-gray-500 rounded-full typing-dot" />
                    <span className="w-1.5 h-1.5 bg-gray-500 rounded-full typing-dot" />
                  </div>
                </div>
              </div>
            )}

            {/* ── Failed stream recovery ── */}
            {streamFailed && lastPrompt && (
              <div className="flex gap-4 w-full chat-msg-enter items-start pt-1 pb-3">
                <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center bg-red-500/10 border border-red-500/20 text-red-400 shadow select-none">
                  <AlertCircle size={15} />
                </div>
                <div className="flex-1 min-w-0 flex flex-col gap-2">
                  <div className="px-4 py-3 bg-red-500/5 border border-red-500/15 rounded-2xl rounded-bl-[4px] shadow-sm space-y-2 max-w-md">
                    <p className="text-xs font-semibold text-red-300 select-none">Stream interrupted</p>
                    <p className="text-[11px] text-gray-400 leading-relaxed select-none">
                      Transient LLM rate limit or connection drop. Your thread is safe.
                    </p>
                    <button
                      onClick={() => handleSendMessage(null, lastPrompt)}
                      className="px-3 py-1.5 bg-red-500/15 hover:bg-red-500/25 border border-red-500/25 rounded-lg text-[11px] font-semibold text-red-300 flex items-center gap-1.5 transition-all hover:scale-[1.02]"
                    >
                      <RefreshCw size={10} className="animate-spin-slow" />
                      Regenerate
                    </button>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} className="h-2" />
          </div>
        </div>

        {/* ──────────── Input Bar & Centered Welcome Screen ──────────── */}
        <div className={messages.length === 0 && !isLoadingMessages ? "flex flex-col items-center justify-center flex-1 w-full px-4" : "w-full"}>
          
          {messages.length === 0 && !isLoadingMessages && (
            <div className="flex flex-col items-center text-center space-y-2 mb-10 animate-in fade-in duration-1000 select-none">
              <h2 className="text-4xl sm:text-5xl font-semibold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-blue-500 to-purple-500 pb-1 drop-shadow-sm">
                Hello, {user?.full_name?.split(' ')[0] || user?.email?.split('@')[0] || 'there'}
              </h2>
              <h3 className="text-4xl sm:text-5xl font-medium tracking-tight text-gray-500/60 drop-shadow-sm">
                What’s the plan today?
              </h3>
            </div>
          )}

          <div className="w-full relative max-w-3xl mx-auto">
            {messages.length === 0 && !isLoadingMessages && (
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[90%] md:w-[70%] h-[160%] -z-10 pointer-events-none select-none">
                <div 
                  className="w-full h-full mix-blend-screen"
                  style={{
                    background: 'radial-gradient(ellipse at center, rgba(0, 255, 255, 0.15) 0%, rgba(0, 102, 255, 0.15) 30%, rgba(138, 43, 226, 0.05) 60%, transparent 80%)',
                    filter: 'blur(50px)',
                    animation: 'auraPulse 8s ease-in-out infinite'
                  }}
                />
              </div>
            )}
            <ChatInput
              inputMessage={inputMessage}
              setInputMessage={setInputMessage}
              handleSendMessage={handleSendMessage}
              isStreaming={isStreaming}
              handleStopGeneration={handleStopGeneration}
              attachments={attachments}
              removeAttachment={removeAttachment}
              handleFileSelect={handleFileSelect}
              isDragging={isDragging}
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onDrop={onDrop}
            />
          </div>
        </div>

      </main>

      {/* Reset Password Modal */}
      <ResetPasswordModal
        isOpen={isResetPasswordOpen}
        onClose={() => setIsResetPasswordOpen(false)}
      />

      {/* PDF Upload Modal */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={fetchDocuments}
        token={token}
      />

      {/* Document Preview Drawer */}
      <DocumentPreview
        isOpen={isPreviewOpen}
        docId={previewDocId}
        docName={previewDocName}
        token={token}
        onClose={() => {
          setIsPreviewOpen(false);
          setPreviewDocId(null);
          setPreviewDocName(null);
        }}
      />

      {/* Settings Modal */}
      <SettingsModal 
        isOpen={isSettingsOpen} 
        onClose={() => setIsSettingsOpen(false)} 
        user={user} 
        onLogout={handleLogout} 
      />

    </div>
  );
}
