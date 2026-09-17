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
      // Return them to wherever the guard intercepted them.
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
      subtitle="Sign in to pick up your recommendations where you left them."
      footer={
        <>
          New here?{' '}
          <Link to="/signup" className="font-medium text-violet-400 hover:text-violet-300">
            Create an account
          </Link>
        </>
      }
      aside={
        <blockquote className="max-w-sm">
          <p className="font-display text-3xl leading-snug text-white/85">
            “The best recommendation is the one you can argue with.”
          </p>
          <footer className="mt-5 text-2xs text-white/35">
            Every MOVICO pick tells you which of your films it came from.
          </footer>
        </blockquote>
      }
    >
      <form onSubmit={submit} className="space-y-4" noValidate>
        <div>
          <label htmlFor="username" className="mb-1.5 block text-2xs font-medium text-white/60">
            Username
          </label>
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
          <label htmlFor="password" className="mb-1.5 block text-2xs font-medium text-white/60">
            Password
          </label>
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
          <p
            role="alert"
            className="flex items-start gap-2 rounded-xl border border-magenta-500/25 bg-magenta-500/[0.08] px-3.5 py-2.5 text-2xs leading-relaxed text-magenta-400"
          >
            <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            {error}
          </p>
        )}

        <button type="submit" disabled={busy} className="btn-primary w-full py-3">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>

      <p className="mt-6 text-center text-2xs text-white/30">
        Just looking?{' '}
        <Link to="/discover" className="text-white/50 underline underline-offset-2 hover:text-white">
          Browse without an account
        </Link>
      </p>
    </AuthShell>
  );
}
