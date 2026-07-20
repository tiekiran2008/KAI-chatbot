"use client";

import React, { createContext, useContext, useState, useEffect } from "react";

const SettingsContext = createContext({});

export function SettingsProvider({ children }) {
  const [settings, setSettings] = useState({
    theme: "system",
    accent_color: "#1d4ed8",
    font_size: "14",
    ai_model: "gemini-2.5-flash",
    temperature: 1.0,
    max_tokens: 8192,
    system_prompt: "",
    voice_input: true,
    voice_output: false,
    speech_speed: 1.0,
    memory_enabled: true
  });
  const [isLoading, setIsLoading] = useState(true);

  // Load settings on mount if user is logged in
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      setIsLoading(false);
      return;
    }
    
    fetch("http://localhost:8000/api/v1/settings", {
      headers: { "Authorization": `Bearer ${token}` }
    })
    .then(res => res.json())
    .then(data => {
      if (data.settings && Object.keys(data.settings).length > 0) {
        setSettings(prev => ({ ...prev, ...data.settings }));
      }
    })
    .catch(err => console.error("Failed to load settings", err))
    .finally(() => setIsLoading(false));
  }, []);

  // Update Settings handler
  const updateSettings = async (newSettings) => {
    setSettings(prev => ({ ...prev, ...newSettings }));
    const token = localStorage.getItem("token");
    if (!token) return;

    try {
      await fetch("http://localhost:8000/api/v1/settings", {
        method: "POST",
        headers: { 
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ settings: newSettings })
      });
    } catch (err) {
      console.error("Failed to save settings to server", err);
    }
  };

  // Apply Theme and Styling
  useEffect(() => {
    const root = document.documentElement;

    // Apply theme
    let isDark = false;
    if (settings.theme === "dark") {
      isDark = true;
    } else if (settings.theme === "system") {
      isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    }

    if (isDark) {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }

  }, [settings.theme]);

  return (
    <SettingsContext.Provider value={{ settings, updateSettings, isLoading }}>
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  return useContext(SettingsContext);
}
