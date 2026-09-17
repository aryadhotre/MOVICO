import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { AlertCircle, ArrowRight, Loader2 } from 'lucide-react';
import AuthShell from '../components/AuthShell';
import { useAuth } from '../lib/auth';

export default function Login() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ username: '', password: '' });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await signIn(form.username.trim(), form.password);
      // Return them to wherever the route guard intercepted them.
      navigate(location.state?.from || '/app', { replace: true });
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Pick up your selections where you left them."
      footer={
        <>
          No account yet?{' '}
          <Link to="/signup" className="text-tungsten-400 underline decoration-tungsten-500/40 underline-offset-4 hover:text-tungsten-300">
            Create one
          </Link>
        </>
      }
      aside={
        <blockquote className="max-w-sm">
          <p className="font-display text-[1.75rem] font-light leading-snug text-print-100">
            “The best recommendation is the one you can argue with.”
          </p>
          <footer className="tech mt-6 normal-case">
            Every pick names the films of yours it came from.
          </footer>
        </blockquote>
      }
    >
      <form onSubmit={submit} className="space-y-5" noValidate>
        <div>
          <label htmlFor="username" className="tech mb-2 block">Username</label>
          <input
            id="username"
            name="username"
            autoComplete="username"
            required
            value={form.username}
            onChange={(event) => setForm({ ...form, username: event.target.value })}
            className="input"
            placeholder="your username"
          />
        </div>

        <div>
          <label htmlFor="password" className="tech mb-2 block">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={form.password}
            onChange={(event) => setForm({ ...form, password: event.target.value })}
            className="input"
            placeholder="••••••••"
          />
        </div>

        {error && (
          <p role="alert" className="flex items-start gap-2 border border-reel-500/40 bg-reel-500/10 px-3.5 py-2.5 font-mono text-2xs leading-relaxed text-reel-400">
            <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            {error}
          </p>
        )}

        <button type="submit" disabled={busy} className="btn-primary w-full">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>

      <p className="tech mt-8 text-center normal-case">
        Just looking?{' '}
        <Link to="/discover" className="text-print-200 underline underline-offset-4 hover:text-tungsten-400">
          Browse without an account
        </Link>
      </p>
    </AuthShell>
  );
}
