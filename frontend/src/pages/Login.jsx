import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login, register } from '../api/auth';
import { User, Lock, Mail, AlertCircle, ArrowRight } from 'lucide-react';
import Logo from '../components/Logo';

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

  // Sample backdrops for the collage
  const backdrops = [
    'https://image.tmdb.org/t/p/original/8ZTVqvKdQ8emSGUOMJsS4VOWHpG.jpg', // Inception
    'https://image.tmdb.org/t/p/original/rAiYTfKGqDCRIIqo664sY9XZIvQ.jpg', // Interstellar
    'https://image.tmdb.org/t/p/original/xJHokMbljvjEVAZS3xNCi30nGR.jpg', // Dune
    'https://image.tmdb.org/t/p/original/7RyHsO4yDXtBv1zUU3mTpHeQ0d5.jpg', // Avengers
  ];

  return (
    <div className="h-screen w-full bg-black flex flex-col font-sans">
      {/* Top Letterbox Bar */}
      <div className="h-7 w-full bg-black shrink-0 z-50"></div>

      {/* Main Split Screen */}
      <div className="flex-1 flex overflow-hidden relative bg-[#0B0E14]">
        
        {/* Left Side: Cinematic Backdrop Collage (Hidden on small screens) */}
        <div className="hidden lg:block w-[55%] relative overflow-hidden bg-black">
          <div className="absolute inset-0 grid grid-cols-2 grid-rows-2 gap-1 opacity-40 animate-slow-pan scale-110 blur-[2px]">
            {backdrops.map((src, i) => (
              <div 
                key={i} 
                className="w-full h-full bg-cover bg-center"
                style={{ backgroundImage: `url(${src})` }}
              />
            ))}
          </div>
          {/* Gradients to fade into the right side and darken */}
          <div className="absolute inset-0 bg-gradient-to-r from-black/20 via-black/40 to-[#0B0E14] z-10" />
          <div className="absolute inset-0 bg-gradient-to-t from-[#0B0E14] via-transparent to-[#0B0E14] opacity-50 z-10" />
        </div>

        {/* Right Side: Form Panel */}
        <div className="w-full lg:w-[45%] flex flex-col justify-center p-8 md:p-16 lg:p-20 relative z-20 overflow-y-auto">
          {/* Logo */}
          <div className="absolute top-8 left-8 md:top-12 md:left-16 lg:top-16 lg:left-20">
            <Logo className="text-4xl md:text-5xl" />
          </div>

          <div className="w-full max-w-sm mt-16 lg:mt-8">
            <h1 className="font-display text-5xl md:text-6xl text-white mb-2 uppercase tracking-wide">
              {isRegistering ? 'Join the Premiere' : 'Welcome Back'}
            </h1>
            <p className="text-text-secondary text-sm mb-10 font-medium">
              {isRegistering 
                ? 'Sign up for a personalized, AI-curated cinematic experience.' 
                : 'Sign in to access your curated dashboard and watchlist.'}
            </p>

            {error && (
              <div className="flex items-center gap-3 bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded-xl mb-6">
                <AlertCircle size={16} className="shrink-0" />
                <span className="text-sm font-medium">{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="block text-xs font-bold text-text-secondary uppercase tracking-widest mb-2">Username</label>
                <div className="relative">
                  <User size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-text-secondary/50" />
                  <input
                    type="text"
                    required
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="w-full bg-white/[0.03] border border-white/[0.08] rounded-xl py-3 pl-12 pr-4 text-sm text-white placeholder:text-text-secondary/30 focus:outline-none focus:border-accent-gold/50 focus:bg-white/[0.05] focus:ring-1 focus:ring-accent-gold/20 transition-all duration-200 font-medium"
                    placeholder="Enter your username"
                  />
                </div>
              </div>

              {isRegistering && (
                <div>
                  <label className="block text-xs font-bold text-text-secondary uppercase tracking-widest mb-2">Email</label>
                  <div className="relative">
                    <Mail size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-text-secondary/50" />
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full bg-white/[0.03] border border-white/[0.08] rounded-xl py-3 pl-12 pr-4 text-sm text-white placeholder:text-text-secondary/30 focus:outline-none focus:border-accent-gold/50 focus:bg-white/[0.05] focus:ring-1 focus:ring-accent-gold/20 transition-all duration-200 font-medium"
                      placeholder="Enter your email"
                    />
                  </div>
                </div>
              )}

              <div>
                <label className="block text-xs font-bold text-text-secondary uppercase tracking-widest mb-2">Password</label>
                <div className="relative">
                  <Lock size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-text-secondary/50" />
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full bg-white/[0.03] border border-white/[0.08] rounded-xl py-3 pl-12 pr-4 text-sm text-white placeholder:text-text-secondary/30 focus:outline-none focus:border-accent-gold/50 focus:bg-white/[0.05] focus:ring-1 focus:ring-accent-gold/20 transition-all duration-200 font-medium"
                    placeholder="Enter your password"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full btn-gold flex items-center justify-center gap-2 text-black font-bold text-sm tracking-wide py-3.5 rounded-xl mt-8 disabled:opacity-50"
              >
                {loading ? 'PROCESSING...' : (isRegistering ? 'CREATE ACCOUNT' : 'SIGN IN')}
                {!loading && <ArrowRight size={18} />}
              </button>
            </form>

            <div className="mt-8">
              <button
                onClick={() => {
                  setIsRegistering(!isRegistering);
                  setError('');
                }}
                className="text-sm font-medium text-text-secondary/70 hover:text-accent-gold transition-colors"
              >
                {isRegistering 
                  ? 'Already have an account? Sign In' 
                  : "Don't have an account? Sign Up"}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile-only background overlay since left panel is hidden */}
        <div className="block lg:hidden absolute inset-0 z-0 bg-cover bg-center opacity-10 blur-sm animate-slow-pan"
             style={{ backgroundImage: `url(${backdrops[0]})` }} />
        <div className="block lg:hidden absolute inset-0 z-10 bg-[#0B0E14]/90" />
      </div>

      {/* Bottom Letterbox Bar */}
      <div className="h-7 w-full bg-black shrink-0 z-50"></div>
    </div>
  );
}
