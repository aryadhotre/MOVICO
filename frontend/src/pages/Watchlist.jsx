import React from 'react';
import WatchlistPanel from '../components/WatchlistPanel';

export default function Watchlist() {
  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-text-primary">My Watchlist</h1>
        <p className="text-text-secondary mt-1">Movies you want to watch later.</p>
      </div>
      <div className="grid grid-cols-1">
        <WatchlistPanel />
      </div>
      {/* In a real app we'd add the full paginated list below */}
    </div>
  );
}
