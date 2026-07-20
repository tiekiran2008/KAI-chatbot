// src/app/page.jsx
'use client';

import '@/styles/loginCard.css';
import MagneticButton from '@/components/MagneticButton';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { supabase, isSupabaseEnabled } from '@/lib/supabase';
import { motion } from 'framer-motion';
import ResetPasswordModal from '@/components/ResetPasswordModal';

export default function AuthPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLogin, setIsLogin] = useState(true);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [isResetPasswordOpen, setIsResetPasswordOpen] = useState(false);

  useEffect(() => {
    const checkUser = async () => {
      if (isSupabaseEnabled()) {
        const { data: { session } } = await supabase.auth.getSession();
        if (session) router.push('/chat');
      }
    };
    checkUser();
  }, [router]);

  const handleGoogleSignIn = async () => {
    if (!isSupabaseEnabled()) {
      setError('Supabase not configured.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}/chat`,
        },
      });
      if (error) throw error;
    } catch (err) {
      setError(err.message || 'Google sign-in error');
      setLoading(false);
    }
  };

  const handleAuth = async (e) => {
    e.preventDefault();
    if (!isSupabaseEnabled()) {
      setError('Supabase not configured.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      if (isLogin) {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        router.push('/chat');
      } else {
        const { error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
        router.push('/chat');
      }
    } catch (err) {
      setError(err.message || 'Authentication error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      className="flex items-center justify-center w-screen h-screen bg-background relative text-white overflow-hidden"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.8, ease: 'easeOut' }}
    >
      {/* Ambient Lighting & Radial Glow */}
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

      {/* Vignette Overlay */}
      <div 
        className="absolute inset-0 z-0 pointer-events-none"
        style={{ background: 'radial-gradient(circle at center, transparent 0%, rgba(0,0,0,0.4) 100%)' }}
      />
      <div className="login-card w-full max-w-md p-8 space-y-6 relative z-10">
        <div className="flex justify-center mb-6 mt-2">
          <div className="logo-container p-3">
            <img src="/logo.png" alt="AI Chatbot" className="h-20 w-20 logo-animate relative z-10" />
          </div>
        </div>
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2, ease: "easeOut" }}
          className="text-center space-y-2 mb-6"
        >
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight drop-shadow-[0_0_15px_rgba(255,255,255,0.3)]">
            {isLogin ? 'Welcome to KAI Chatbot' : 'Join KAI Chatbot'}
          </h2>
          <p className="text-xs sm:text-sm text-gray-300/90 font-medium tracking-wide drop-shadow-sm px-2">
            Your Intelligent AI Assistant powered by Kiran Artificial Intelligence
          </p>
        </motion.div>
        {error && (
          <div className="p-4 text-sm text-red-400 bg-red-900/50 rounded-lg border border-red-800">
            {error}
          </div>
        )}
        <form className="space-y-4" onSubmit={handleAuth}>
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-1">
              Email address
            </label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-cyan-400"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-300 mb-1">
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-cyan-400"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <div className="flex items-center justify-between">
            <label className="flex items-center text-gray-300">
              <input type="checkbox" className="h-4 w-4 text-cyan-500" />
              <span className="ml-2 text-sm">Remember me</span>
            </label>
            <button
              type="button"
              onClick={() => setIsResetPasswordOpen(true)}
              className="text-sm font-medium text-cyan-400 hover:underline"
            >
              Forgot password?
            </button>
          </div>
          <MagneticButton type="submit" disabled={loading} className="w-full flex justify-center">
            {loading ? 'Processing...' : (isLogin ? 'Sign In' : 'Sign Up')}
          </MagneticButton>
        </form>

        <div className="flex items-center my-4">
          <div className="flex-grow border-t border-gray-700"></div>
          <span className="px-3 text-sm text-gray-400">OR</span>
          <div className="flex-grow border-t border-gray-700"></div>
        </div>

        <MagneticButton
          type="button"
          onClick={handleGoogleSignIn}
          disabled={loading}
          className="w-full flex items-center justify-center !bg-white !bg-none !text-gray-800 hover:!bg-gray-100"
        >
          <svg className="h-5 w-5 mr-2" viewBox="0 0 533.5 544.3" xmlns="http://www.w3.org/2000/svg">
            <path fill="#4285F4" d="M533.5 278.4c0-17.5-1.5-34.5-4.3-50.9H272v96.2h147.8c-6.4 34.9-25.6 64.4-54.4 84.2v69.9h87.9c51.6-47.5 81.2-117.5 81.2-199.4z" />
            <path fill="#34A853" d="M272 544.3c73.2 0 134.6-24.2 179.5-65.7l-87.9-69.9c-24.4 16.3-55.5 26-91.6 26-70.4 0-130.1-47.5-151.5-111.5H30.9v70.2C75.9 489.6 167.8 544.3 272 544.3z" />
            <path fill="#FBBC05" d="M120.5 322.2c-5.4-15.8-8.5-32.7-8.5-50.2s3.1-34.4 8.5-50.2v-72H30.9C11.2 185.9 0 228.5 0 272s11.2 86.1 30.9 122H120.5v-71.8z" />
            <path fill="#EA4335" d="M272 108.3c38.2 0 72.4 13.1 99.3 38.9l74.3-74.3C399.3 28.5 339.3 0 272 0 168.2 0 76.5 54.6 30.9 134.5l89.6 69.6C142 140.4 201.3 108.3 272 108.3z" />
          </svg>
          Continue with Google
        </MagneticButton>
        <div className="text-center mt-4">
          <button
            type="button"
            onClick={() => { setIsLogin(!isLogin); setError(''); }}
            className="text-sm font-medium text-cyan-400 hover:text-cyan-300"
          >
            {isLogin ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
          </button>
        </div>
      </div>
      <ResetPasswordModal
        isOpen={isResetPasswordOpen}
        onClose={() => setIsResetPasswordOpen(false)}
      />
    </motion.div>
  );
}
