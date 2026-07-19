import React, { useState, useEffect, useCallback } from 'react';
import { getRecommendations } from '../api/recommendations';
import { getHistory } from '../api/ratings';
import { getMovieById } from '../api/movies';
import GlassCard from '../components/GlassCard';
import ExplanationPanel from '../components/ExplanationPanel';
import { useRating } from '../context/RatingContext';
import { Sparkles, Star, RefreshCw, AlertCircle, X } from 'lucide-react';
import { Link } from 'react-router-dom';

function RecommendationTypeBadge({ type }) {
  const labels = {
    hybrid: { label: 'Hybrid Pick', color: 'text-accent-primary border-accent-primary/30 bg-accent-primary/10' },
    collaborative: { label: 'Fans Like You', color: 'text-blue-400 border-blue-400/30 bg-blue-400/10' },
    content: { label: 'Content Match', color: 'text-cyan-400 border-cyan-400/30 bg-cyan-400/10' },
    popularity: { label: 'Popular Now', color: 'text-yellow-400 border-yellow-400/30 bg-yellow-400/10' },
    popularity_cold_start: { label: 'Popular — New User', color: 'text-yellow-400 border-yellow-400/30 bg-yellow-400/10' },
  };
  const style = labels[type] || { label: type, color: 'text-text-secondary border-white/20 bg-white/5' };
  return (
    <span className={`text-xs font-bold px-3 py-1.5 rounded-full border uppercase tracking-wider ${style.color}`}>
      {style.label}
    </span>
  );
}

import MovieCard from '../components/MovieCard';

export default function Recommendations() {
  const { ratingVersion, error: ratingError, clearError } = useRating();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [topGenres, setTopGenres] = useState([]);

  const fetchRecs = useCallback(async (bypass = false) => {
    if (bypass) setRefreshing(true);
    else setLoading(true);
    setError('');
    try {
      const res = await getRecommendations({ limit: 12, bypassCache: bypass, includeExplanations: true });
      setData(res);
    } catch (e) {
      setError('Failed to fetch personalized recommendations.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Derive top genres from rating history
  useEffect(() => {
    async function deriveGenres() {
      try {
        const history = await getHistory();
        const highRated = (history.items || []).filter(r => r.rating >= 4);
        if (highRated.length === 0) return;

        // Fetch movie details for high-rated entries (up to 20)
        const movieIds = highRated.slice(0, 20).map(r => r.movie_id);
        const movies = await Promise.all(movieIds.map(id => getMovieById(id).catch(() => null)));

        // Count genres
        const genreCounts = {};
        movies.forEach(movie => {
          if (!movie || !movie.genres) return;
          movie.genres.split('|').forEach(g => {
            const genre = g.trim();
            if (genre) genreCounts[genre] = (genreCounts[genre] || 0) + 1;
          });
        });

        const sorted = Object.entries(genreCounts)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 4)
          .map(([name]) => name);
        setTopGenres(sorted);
      } catch (_) {}
    }
    deriveGenres();
  }, []);

  useEffect(() => { fetchRecs(false); }, [fetchRecs, ratingVersion]); // re-fetch when rating version bumps

  return (
    <div className="max-w-7xl mx-auto space-y-16">
      {/* Inline error banner from rating context */}
      {ratingError && (
        <div className="flex items-center gap-3 bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-xl">
          <AlertCircle size={18} className="shrink-0" />
          <span className="text-sm flex-1">{ratingError}</span>
          <button onClick={clearError} className="hover:text-red-300 transition-colors">
            <X size={16} />
          </button>
        </div>
      )}
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-text-primary flex items-center gap-3 tracking-tight">
            <Sparkles className="text-accent-primary" />
            Top Picks For You
          </h1>
          <p className="text-text-secondary mt-1">Powered by your taste and our AI engine.</p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {data?.recommendation_type && (
            <RecommendationTypeBadge type={data.recommendation_type} />
          )}
          <button
            onClick={() => fetchRecs(true)}
            disabled={refreshing}
            className="btn-gold flex items-center gap-2 text-black px-4 py-2 rounded-xl text-sm font-semibold"
          >
            <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
            {refreshing ? 'Refreshing...' : 'Refresh Picks'}
          </button>
        </div>
      </div>

      {/* Why These Match — derived from history */}
      {topGenres.length > 0 && (
        <GlassCard className="p-5 flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="shrink-0">
            <p className="text-xs uppercase tracking-widest text-text-secondary font-semibold mb-1">Why These Match</p>
            <p className="text-sm text-text-primary font-medium">You often rate these genres highly:</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {topGenres.map(genre => (
              <span key={genre} className="flex items-center gap-1 bg-accent-primary/15 border border-accent-primary/25 text-accent-primary px-3 py-1 rounded-full text-sm font-semibold">
                ★ {genre}
              </span>
            ))}
          </div>
        </GlassCard>
      )}

      {/* Movie Grid */}
      {loading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {Array.from({ length: 12 }).map((_, i) => (
            <GlassCard key={i} className="aspect-[2/3] animate-pulse bg-white/5 p-0" />
          ))}
        </div>
      ) : error ? (
        <GlassCard className="p-8 text-center text-red-400 font-medium">{error}</GlassCard>
      ) : !data?.movies?.length ? (
        <GlassCard className="p-12 text-center">
          <Sparkles className="mx-auto text-text-secondary mb-4" size={48} />
          <p className="text-text-primary font-semibold mb-1">Nothing to show yet!</p>
          <p className="text-text-secondary text-sm">Rate a few movies and come back — your AI picks will appear here.</p>
        </GlassCard>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-6 grid-flow-dense">
          {data.movies.map((movie, index) => {
            const matchPct = movie.explanation?.similarity_score
              ? Math.round(movie.explanation.similarity_score * 100)
              : null;
            const isTopPick = index === 0;
            return (
              <div key={movie.id} className={isTopPick ? 'col-span-2 row-span-2 md:col-span-2 md:row-span-2' : 'col-span-1 row-span-1'}>
                <MovieCard movie={movie} rank={index + 1} matchPct={matchPct} />
              </div>
            );
          })}
        </div>
      )}

      {/* Explainability for first movie */}
      {!loading && data?.movies?.length > 0 && data.movies[0].explanation && (
        <div>
          <h2 className="section-header mb-5">AI Insight — Top Pick</h2>
          <ExplanationPanel movie={data.movies[0]} />
        </div>
      )}
    </div>
  );
}
