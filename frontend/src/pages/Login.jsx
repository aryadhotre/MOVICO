import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login, register } from '../api/auth';
import { Film, User, Lock, Mail, AlertCircle, ArrowRight } from 'lucide-react';
import GlassCard from '../components/GlassCard';

export default function Login() {
  const [isRegistering, setIsRegistering] = useState(false);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isRegistering) {
        await register(username, email, password);
        await login(username, password); // auto-login after register
      } else {
        await login(username, password);
      }
      navigate('/'); // Redirect to protected area
    } catch (err) {
      setError(err?.message || (isRegistering ? 'Registration failed.' : 'Invalid credentials.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0B0E14] flex items-center justify-center p-4 relative overflow-hidden">
      {/* Ambient glow orbs */}
      <div className="absolute top-[20%] left-[30%] w-[500px] h-[500px] bg-accent-primary/[0.12] rounded-full blur-[150px] pointer-events-none" />
      <div className="absolute bottom-[20%] right-[25%] w-[400px] h-[400px] bg-accent-primaryHover/[0.08] rounded-full blur-[130px] pointer-events-none" />
      
      <div className="w-full max-w-md z-10">
        <div className="text-center mb-8 flex flex-col items-center">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-accent-primary to-accent-primaryHover flex items-center justify-center shadow-[0_0_30px_rgba(139,92,246,0.4)] mb-5">
            <Film size={26} className="text-white" />
          </div>
          <h1 className="text-3xl font-bold tracking-[0.2em] text-text-primary mb-1">MOVICO</h1>
          <p className="text-text-secondary/60 text-sm">Your personalized movie experience.</p>
        </div>

        <GlassCard className="p-8">
          <h2 className="text-xl font-bold text-white mb-1">
            {isRegistering ? 'Create an account' : 'Welcome back'}
          </h2>
          <p className="text-text-secondary/50 text-sm mb-6">
            {isRegistering ? 'Sign up to get personalized recommendations.' : 'Sign in to continue to your dashboard.'}
          </p>

          {error && (
            <div className="flex items-center gap-3 bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded-xl mb-5">
              <AlertCircle size={16} className="shrink-0" />
              <span className="text-sm">{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-[11px] font-semibold text-text-secondary/70 uppercase tracking-wider mb-2">Username</label>
              <div className="relative">
                <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary/40" />
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full bg-white/[0.03] border border-white/[0.08] rounded-xl py-2.5 pl-10 pr-4 text-sm text-white placeholder:text-text-secondary/30 focus:outline-none focus:border-accent-primary/40 focus:bg-white/[0.05] transition-all duration-200"
                  placeholder="Enter your username"
                />
              </div>
            </div>

            {isRegistering && (
              <div>
                <label className="block text-[11px] font-semibold text-text-secondary/70 uppercase tracking-wider mb-2">Email</label>
                <div className="relative">
                  <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary/40" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full bg-white/[0.03] border border-white/[0.08] rounded-xl py-2.5 pl-10 pr-4 text-sm text-white placeholder:text-text-secondary/30 focus:outline-none focus:border-accent-primary/40 focus:bg-white/[0.05] transition-all duration-200"
                    placeholder="Enter your email"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-[11px] font-semibold text-text-secondary/70 uppercase tracking-wider mb-2">Password</label>
              <div className="relative">
                <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary/40" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-white/[0.03] border border-white/[0.08] rounded-xl py-2.5 pl-10 pr-4 text-sm text-white placeholder:text-text-secondary/30 focus:outline-none focus:border-accent-primary/40 focus:bg-white/[0.05] transition-all duration-200"
                  placeholder="Enter your password"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full btn-gradient flex items-center justify-center gap-2 text-white font-semibold py-3 rounded-xl mt-6 text-sm"
            >
              {loading ? 'Processing...' : (isRegistering ? 'Create Account' : 'Sign In')}
              {!loading && <ArrowRight size={16} />}
            </button>
          </form>

          <div className="mt-6 text-center">
            <button
              onClick={() => {
                setIsRegistering(!isRegistering);
                setError('');
              }}
              className="text-sm text-text-secondary/60 hover:text-white transition-colors"
            >
              {isRegistering 
                ? 'Already have an account? Sign In' 
                : "Don't have an account? Sign Up"}
            </button>
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
