import { Link } from 'react-router-dom';
import { Home, Search } from 'lucide-react';
import Logo from '../components/Logo';

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
      <Logo size={34} showWordmark={false} />
      <p className="title-card mt-10 text-7xl text-tungsten-500">404</p>
      <h1 className="title-card mt-5 text-2xl text-print-50">Reel missing</h1>
      <p className="mt-4 max-w-sm text-pretty text-sm leading-relaxed text-print-400">
        This print was never struck, or the page has moved. The catalogue is still
        where you left it.
      </p>
      <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
        <Link to="/" className="btn-primary">
          <Home className="h-4 w-4" />
          Back to start
        </Link>
        <Link to="/discover" className="btn-secondary">
          <Search className="h-4 w-4" />
          Browse films
        </Link>
      </div>
    </div>
  );
}
