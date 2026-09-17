import { Link } from 'react-router-dom';
import { Home, Search } from 'lucide-react';
import Logo from '../components/Logo';

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
      <Logo size={34} showWordmark={false} />
      <p className="mt-8 font-display text-7xl italic text-gradient">404</p>
      <h1 className="mt-3 text-2xl font-semibold tracking-tightest text-white">
        This page rolled the credits
      </h1>
      <p className="mt-2.5 max-w-sm text-pretty text-sm leading-relaxed text-white/45">
        The link is broken or the page moved. The catalogue is still where you left it.
      </p>
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Link to="/" className="btn-primary px-5 py-2.5">
          <Home className="h-4 w-4" />
          Back to start
        </Link>
        <Link to="/discover" className="btn-secondary px-5 py-2.5">
          <Search className="h-4 w-4" />
          Browse films
        </Link>
      </div>
    </div>
  );
}
