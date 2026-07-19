import React, { useState, useEffect } from 'react';
import { getWatchlist, removeFromWatchlist } from '../api/ratings';
import GlassCard from './GlassCard';
import { Link } from 'react-router-dom';
import { Bookmark, X, Star } from 'lucide-react';

export default function WatchlistPanel() {
  const [watchlist, setWatchlist] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await getWatchlist(1, 4); // compact 4 items
        setWatchlist(res.items || []);
      } catch (e) {
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleRemove = async (e, id) => {
    e.preventDefault();
    try {
      await removeFromWatchlist(id);
      setWatchlist(watchlist.filter(item => item.id !== id));
    } catch (e) {
      // ignore
    }
  };

  if (loading) {
    return <GlassCard className="p-6 min-h-[400px] animate-pulse bg-white/5" />;
  }

  return (
    <GlassCard className="p-6 flex flex-col min-h-[400px]">
      <div className="flex items-center justify-between mb-6 shrink-0">
        <h3 className="text-xl font-bold text-text-primary flex items-center gap-2">
          <Bookmark size={20} className="text-accent-secondary" />
          Watchlist
        </h3>
        <Link to="/watchlist" className="text-sm font-semibold text-accent-secondary hover:text-cyan-300 transition-colors">
          Go to Watchlist
        </Link>
      </div>

      {watchlist.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center">
          <Bookmark size={40} className="text-text-secondary mb-4 opacity-50" />
          <p className="text-text-primary font-semibold mb-2">Your watchlist is empty</p>
          <p className="text-text-secondary text-sm">Save movies to watch them later.</p>
        </div>
      ) : (
        <div className="flex-1 flex flex-col gap-4 overflow-y-auto">
          {watchlist.map(item => {
            const movie = item.movie;
            if (!movie) return null;
            return (
              <Link to={`/movies/${movie.id}`} key={item.id} className="group relative flex items-center gap-4 p-2 rounded-lg hover:bg-white/5 transition-colors">
                {movie.poster_url ? (
                  <img src={movie.poster_url} alt={movie.title} className="w-12 h-16 object-cover rounded shadow-md shrink-0" />
                ) : (
                  <div className="w-12 h-16 bg-gray-800 rounded flex items-center justify-center text-[10px] text-text-secondary text-center shrink-0">No Poster</div>
                )}
                <div className="flex-1 min-w-0">
                  <h4 className="text-sm font-bold text-white truncate group-hover:text-accent-primary transition-colors">{movie.title}</h4>
                  <div className="flex items-center gap-3 text-xs text-text-secondary mt-1">
                    <span>{movie.release_date ? movie.release_date.substring(0, 4) : ''}</span>
                    {movie.vote_average > 0 && (
                      <div className="flex items-center gap-1">
                        <Star size={12} className="fill-rating text-rating" />
                        {movie.vote_average.toFixed(1)}
                      </div>
                    )}
                  </div>
                </div>
                <button 
                  onClick={(e) => handleRemove(e, item.id)}
                  className="opacity-0 group-hover:opacity-100 p-2 text-text-secondary hover:text-red-400 hover:bg-red-400/10 rounded-full transition-all shrink-0"
                  title="Remove from watchlist"
                >
                  <X size={16} />
                </button>
              </Link>
            )
          })}
        </div>
      )}
    </GlassCard>
  );
}
