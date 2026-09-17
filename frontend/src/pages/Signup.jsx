import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertCircle, ArrowRight, Check, Loader2 } from 'lucide-react';
import AuthShell from '../components/AuthShell';
import { useAuth } from '../lib/auth';

const PERKS = [
  'Recommendations that explain themselves',
  'Diversity and novelty you control',
  'Every film from 1902 to this month',
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
      // Straight into onboarding: an account with no ratings has nothing to show.
      navigate('/onboarding', { replace: true });
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell
      title="Create your account"
      subtitle="Rate ten films and the engine will have you placed."
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-violet-400 hover:text-violet-300">
            Sign in
          </Link>
        </>
      }
      aside={
        <div className="max-w-sm">
          <p className="font-display text-3xl leading-snug text-white/85">
            Built on 33 million real ratings.
          </p>
          <ul className="mt-8 space-y-3">
            {PERKS.map((perk) => (
              <li key={perk} className="flex items-start gap-2.5 text-sm text-white/55">
                <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-violet-600/25 text-violet-300">
                  <Check className="h-2.5 w-2.5" strokeWidth={3} />
                </span>
                {perk}
              </li>
            ))}
          </ul>
        </div>
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
            minLength={3}
            value={form.username}
            onChange={(event) => setForm({ ...form, username: event.target.value })}
            className="input"
            placeholder="at least 3 characters"
          />
        </div>

        <div>
          <label htmlFor="email" className="mb-1.5 block text-2xs font-medium text-white/60">
            Email
          </label>
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
          <label htmlFor="password" className="mb-1.5 block text-2xs font-medium text-white/60">
            Password
          </label>
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
            <p className="mt-1.5 text-2xs text-amber-500">Use at least 6 characters.</p>
          )}
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

        <button
          type="submit"
          disabled={busy || passwordTooShort}
          className="btn-primary w-full py-3"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
          {busy ? 'Creating account…' : 'Create account'}
        </button>
      </form>
    </AuthShell>
  );
}
