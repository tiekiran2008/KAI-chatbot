'use client';
// src/components/ResetPasswordModal.jsx
// Forgot-password modal that matches the KAI dark aurora theme.
// Only adds password-reset functionality — login/signup logic is untouched.

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Mail, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { supabase, isSupabaseEnabled } from '@/lib/supabase';
import MagneticButton from '@/components/MagneticButton';

/* ─── Error mapping ─────────────────────────────────────────────── */
function getFriendlyError(err) {
  const msg = (err?.message || '').toLowerCase();
  if (msg.includes('invalid email') || msg.includes('unable to validate email'))
    return 'Please enter a valid email address.';
  if (msg.includes('user not found') || msg.includes('email not found'))
    return 'No account found with that email. Please check and try again.';
  if (msg.includes('rate limit') || msg.includes('too many requests') || msg.includes('over email send rate limit'))
    return 'Too many attempts. Please wait a few minutes before trying again.';
  if (msg.includes('network') || msg.includes('fetch') || msg.includes('failed to fetch'))
    return 'Network error. Please check your connection and try again.';
  if (msg.includes('not configured'))
    return 'Authentication service is not configured. Please contact support.';
  return err?.message
    ? err.message.charAt(0).toUpperCase() + err.message.slice(1)
    : 'An unexpected error occurred. Please try again.';
}

/* ─── Email validator ────────────────────────────────────────────── */
const isValidEmail = (val) => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(val);

/* ═══════════════════════════════════════════════════════════════════
   ResetPasswordModal
   Props: isOpen (bool), onClose (fn)
═══════════════════════════════════════════════════════════════════ */
export default function ResetPasswordModal({ isOpen, onClose }) {
  const [email, setEmail]     = useState('');
  const [touched, setTouched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);
  const [success, setSuccess] = useState(false);

  /* Reset all local state when closing */
  const handleClose = () => {
    onClose();
    setTimeout(() => {
      setEmail('');
      setTouched(false);
      setError(null);
      setSuccess(false);
    }, 300);
  };

  /* Inline email validation shown after blur */
  const emailFormatError =
    touched && email && !isValidEmail(email)
      ? 'Please enter a valid email address (e.g. you@example.com).'
      : null;

  /* Send reset link */
  const handleSubmit = async (e) => {
    e.preventDefault();
    setTouched(true);

    if (!email || !isValidEmail(email)) {
      setError('Please enter a valid email address.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      if (!isSupabaseEnabled()) throw new Error('Authentication service not configured');

      const { error: sbError } = await supabase.auth.resetPasswordForEmail(email, {
        // Uncomment and set your update-password page URL when ready:
        // redirectTo: `${window.location.origin}/update-password`,
      });
      if (sbError) throw sbError;

      setSuccess(true);
    } catch (err) {
      console.error('[ResetPassword]', err);
      setError(getFriendlyError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        /* ── Backdrop ── */
        <motion.div
          key="backdrop"
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: 'rgba(5, 8, 22, 0.75)', backdropFilter: 'blur(8px)' }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25 }}
          onClick={(e) => { if (e.target === e.currentTarget) handleClose(); }}
        >
          {/* ── Modal card — matches .login-card glassmorphism ── */}
          <motion.div
            key="modal"
            className="w-full max-w-md relative rounded-2xl text-white"
            style={{
              background: 'rgba(255, 255, 255, 0.07)',
              border: '1px solid rgba(255, 255, 255, 0.18)',
              backdropFilter: 'blur(25px)',
              WebkitBackdropFilter: 'blur(25px)',
              boxShadow: '0 0 24px rgba(0, 255, 255, 0.35), 0 8px 40px rgba(0, 0, 0, 0.6)',
            }}
            initial={{ opacity: 0, scale: 0.93, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.93, y: 20 }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
          >
            {/* Holographic reflection overlay — matches login-card::after */}
            <div
              className="absolute inset-0 rounded-2xl pointer-events-none"
              style={{
                background: 'linear-gradient(135deg, rgba(255,255,255,0.18), rgba(255,255,255,0) 60%)',
                mixBlendMode: 'overlay',
                opacity: 0.6,
              }}
            />

            <div className="relative z-10 p-8 space-y-6">

              {/* ── Header ── */}
              <div className="flex items-start justify-between">
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.1 }}
                >
                  <h2
                    className="text-2xl font-extrabold tracking-tight text-white"
                    style={{ textShadow: '0 0 15px rgba(255,255,255,0.3)' }}
                  >
                    Reset Password
                  </h2>
                  <p className="text-xs text-gray-300/80 font-medium tracking-wide mt-1">
                    Enter your email and we'll send a reset link.
                  </p>
                </motion.div>

                <button
                  onClick={handleClose}
                  disabled={loading}
                  aria-label="Close"
                  className="p-1.5 rounded-full text-gray-400 hover:text-white hover:bg-white/10 transition-colors disabled:opacity-40"
                >
                  <X size={18} />
                </button>
              </div>

              {/* ══ SUCCESS STATE ══ */}
              <AnimatePresence mode="wait">
                {success ? (
                  <motion.div
                    key="success"
                    className="flex flex-col items-center text-center py-6 space-y-4"
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.3 }}
                  >
                    {/* Glowing check icon */}
                    <div
                      className="w-16 h-16 rounded-full flex items-center justify-center"
                      style={{
                        background: 'rgba(0,255,180,0.12)',
                        border: '1px solid rgba(0,255,180,0.3)',
                        boxShadow: '0 0 20px rgba(0,255,180,0.25)',
                      }}
                    >
                      <CheckCircle2 size={34} className="text-emerald-400" />
                    </div>

                    <div>
                      <h3 className="text-base font-bold text-white">Link Sent!</h3>
                      <p className="text-sm text-gray-300 mt-1 leading-relaxed max-w-[280px]">
                        Password reset link sent to{' '}
                        <span className="text-cyan-400 font-semibold break-all">{email}</span>.
                      </p>
                      <p className="text-xs text-gray-500 mt-2">
                        Didn't receive it? Check your spam folder or{' '}
                        <button
                          type="button"
                          onClick={() => { setSuccess(false); setError(null); setEmail(''); setTouched(false); }}
                          className="text-cyan-400 hover:underline"
                        >
                          try again
                        </button>
                        .
                      </p>
                    </div>

                    <MagneticButton type="button" onClick={handleClose} className="w-full mt-2">
                      Close
                    </MagneticButton>
                  </motion.div>

                ) : (
                  /* ══ FORM STATE ══ */
                  <motion.form
                    key="form"
                    onSubmit={handleSubmit}
                    className="space-y-5"
                    noValidate
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    {/* Email field */}
                    <div className="space-y-1.5">
                      <label
                        htmlFor="kai-reset-email"
                        className="block text-sm font-medium text-gray-300"
                      >
                        Email address
                      </label>

                      <div className="relative">
                        <Mail
                          size={16}
                          className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none"
                        />
                        <input
                          id="kai-reset-email"
                          type="email"
                          required
                          autoComplete="email"
                          autoFocus
                          placeholder="you@example.com"
                          value={email}
                          onChange={(e) => { setEmail(e.target.value); setError(null); }}
                          onBlur={() => setTouched(true)}
                          className={`w-full pl-10 pr-4 py-2 rounded-md bg-gray-900 border text-white text-sm
                            placeholder-gray-600 outline-none transition-all duration-200
                            ${emailFormatError || error
                              ? 'border-red-500/70 focus:ring-2 focus:ring-red-500/30'
                              : 'border-gray-700 focus:ring-2 focus:ring-cyan-400'
                            }`}
                        />
                      </div>

                      {/* Inline format error */}
                      <AnimatePresence>
                        {emailFormatError && (
                          <motion.p
                            className="text-[11px] text-red-400 flex items-center gap-1"
                            initial={{ opacity: 0, y: -4 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -4 }}
                          >
                            <AlertCircle size={11} />
                            {emailFormatError}
                          </motion.p>
                        )}
                      </AnimatePresence>
                    </div>

                    {/* API / server error banner */}
                    <AnimatePresence>
                      {error && !emailFormatError && (
                        <motion.div
                          className="p-3 rounded-lg border border-red-800 bg-red-900/40 flex items-start gap-2 text-sm text-red-400"
                          initial={{ opacity: 0, y: -6 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -6 }}
                        >
                          <AlertCircle size={15} className="flex-shrink-0 mt-0.5" />
                          <span>{error}</span>
                        </motion.div>
                      )}
                    </AnimatePresence>

                    {/* Action row */}
                    <div className="flex items-center gap-3 pt-2">
                      {/* Cancel — ghost */}
                      <button
                        type="button"
                        onClick={handleClose}
                        disabled={loading}
                        className="flex-1 py-2 rounded-md border border-gray-700 bg-transparent text-sm font-medium
                          text-gray-300 hover:bg-white/5 hover:border-gray-500 transition-all disabled:opacity-40"
                      >
                        Cancel
                      </button>

                      {/* Send — MagneticButton (purple→pink→cyan gradient, matches login) */}
                      <MagneticButton
                        type="submit"
                        disabled={!email || loading}
                        className="flex-1 flex items-center justify-center gap-2"
                      >
                        {loading ? (
                          <>
                            <Loader2 size={14} className="animate-spin" />
                            Sending…
                          </>
                        ) : (
                          'Send Reset Link'
                        )}
                      </MagneticButton>
                    </div>

                    {/* Back to sign in */}
                    <p className="text-center text-xs text-gray-500 pt-1">
                      Remember your password?{' '}
                      <button
                        type="button"
                        onClick={handleClose}
                        className="text-cyan-400 hover:underline font-medium"
                      >
                        Back to Sign In
                      </button>
                    </p>
                  </motion.form>
                )}
              </AnimatePresence>

            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
