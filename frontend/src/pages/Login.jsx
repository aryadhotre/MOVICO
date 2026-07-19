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
      {/* Background aesthetics */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-accent-primary/20 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-[120px] pointer-events-none" />
      
      <div className="w-full max-w-md z-10">
        <div className="text-center mb-8 flex flex-col items-center">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-accent-primary to-accent-primaryHover flex items-center justify-center shadow-[0_0_20px_rgba(139,92,246,0.5)] mb-4">
            <Film size={24} className="text-white" />
          </div>
          <h1 className="text-3xl font-bold tracking-widest text-text-primary mb-2">MOVICO</h1>
          <p className="text-text-secondary text-sm">Your personalized movie experience.</p>
        </div>

        <GlassCard className="p-8">
          <h2 className="text-2xl font-bold text-white mb-6">
            {isRegistering ? 'Create an account' : 'Welcome back'}
          </h2>

          {error && (
            <div className="flex items-center gap-3 bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg mb-6">
              <AlertCircle size={18} className="shrink-0" />
              <span className="text-sm">{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">Username</label>
              <div className="relative">
                <User size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary" />
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full bg-black/20 border border-white/10 rounded-lg py-2.5 pl-10 pr-4 text-sm text-white focus:outline-none focus:border-accent-primary transition-colors"
                  placeholder="Enter your username"
                />
              </div>
            </div>

            {isRegistering && (
              <div>
                <label className="block text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">Email</label>
                <div className="relative">
                  <Mail size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full bg-black/20 border border-white/10 rounded-lg py-2.5 pl-10 pr-4 text-sm text-white focus:outline-none focus:border-accent-primary transition-colors"
                    placeholder="Enter your email"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">Password</label>
              <div className="relative">
                <Lock size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-black/20 border border-white/10 rounded-lg py-2.5 pl-10 pr-4 text-sm text-white focus:outline-none focus:border-accent-primary transition-colors"
                  placeholder="Enter your password"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 bg-accent-primary hover:bg-accent-primaryHover text-white font-semibold py-3 rounded-lg transition-colors mt-6 disabled:opacity-50"
            >
              {loading ? 'Processing...' : (isRegistering ? 'Sign Up' : 'Sign In')}
              {!loading && <ArrowRight size={18} />}
            </button>
          </form>

          <div className="mt-6 text-center">
            <button
              onClick={() => {
                setIsRegistering(!isRegistering);
                setError('');
              }}
              className="text-sm text-text-secondary hover:text-white transition-colors"
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
