import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertCircle, ArrowRight, Loader2 } from 'lucide-react';
import AuthShell from '../components/AuthShell';
import { useAuth } from '../lib/auth';

const PERKS = [
  ['I', 'Recommendations that name their sources'],
  ['II', 'Diversity and novelty under your control'],
  ['III', 'Every film from 1902 to this month'],
];

export default function Signup() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: '', email: '', password: '' });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const passwordTooShort = form.password.length > 0 && form.password.length < 6;

  const submit = async (event) => {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await register({
        username: form.username.trim(),
        email: form.email.trim(),
        password: form.password,
      });
      // Straight into calibration: an account with no ratings has nothing to show.
      navigate('/onboarding', { replace: true });
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell
      title="Create an account"
      subtitle="Rate ten films and the model has you placed."
      footer={
        <>
          Already have one?{' '}
          <Link to="/login" className="text-tungsten-400 underline decoration-tungsten-500/40 underline-offset-4 hover:text-tungsten-300">
            Sign in
          </Link>
        </>
      }
      aside={
        <div className="max-w-sm">
          <p className="font-display text-[1.75rem] font-light leading-snug text-print-100">
            Built on 33 million real ratings.
          </p>
          <ul className="mt-10 space-y-5">
            {PERKS.map(([numeral, text]) => (
              <li key={numeral} className="flex items-baseline gap-4">
                <span className="w-6 shrink-0 font-display text-sm text-tungsten-500">{numeral}</span>
                <span className="text-sm leading-relaxed text-print-300">{text}</span>
              </li>
            ))}
          </ul>
        </div>
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
            minLength={3}
            value={form.username}
            onChange={(event) => setForm({ ...form, username: event.target.value })}
            className="input"
            placeholder="at least 3 characters"
          />
        </div>

        <div>
          <label htmlFor="email" className="tech mb-2 block">Email</label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            value={form.email}
            onChange={(event) => setForm({ ...form, email: event.target.value })}
            className="input"
            placeholder="you@example.com"
          />
        </div>

        <div>
          <label htmlFor="password" className="tech mb-2 block">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={6}
            value={form.password}
            onChange={(event) => setForm({ ...form, password: event.target.value })}
            className="input"
            placeholder="at least 6 characters"
            aria-invalid={passwordTooShort}
          />
          {passwordTooShort && (
            <p className="mt-2 font-mono text-2xs text-tungsten-500">Use at least 6 characters.</p>
          )}
        </div>

        {error && (
          <p role="alert" className="flex items-start gap-2 border border-reel-500/40 bg-reel-500/10 px-3.5 py-2.5 font-mono text-2xs leading-relaxed text-reel-400">
            <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            {error}
          </p>
        )}

        <button type="submit" disabled={busy || passwordTooShort} className="btn-primary w-full">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
          {busy ? 'Creating…' : 'Create account'}
        </button>
      </form>
    </AuthShell>
  );
}
