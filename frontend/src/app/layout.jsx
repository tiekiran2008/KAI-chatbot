import './globals.css';
import GlowColorPicker from '@/components/GlowColorPicker';

export const metadata = {
  title: 'KAI CHATBOT',
  description: 'KAI CHATBOT powered by Gemini, FastAPI, and ChromaDB.',
};

import { SettingsProvider } from '@/context/SettingsContext';

export default function RootLayout({ children }) {
  return (
    <html lang="en" className="dark h-full">
      <body className="h-full antialiased font-sans">
        <SettingsProvider>
          {children}
          <GlowColorPicker />
        </SettingsProvider>
      </body>
    </html>
  );
}
