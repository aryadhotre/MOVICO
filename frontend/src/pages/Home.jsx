import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getTrending } from '../api/movies';
import { getRecommendations } from '../api/recommendations';
import { getMe } from '../api/auth';
import GlassCard from '../components/GlassCard';
import RatingInsights from '../components/RatingInsights';
import WatchlistPanel from '../components/WatchlistPanel';
import MovieCard from '../components/MovieCard';
import { useRating } from '../context/RatingContext';
import { Star, Clock, Calendar, Play, AlertCircle, X } from 'lucide-react';

export default function Home() {
  const { ratingVersion, error: ratingError, clearError } = useRating();
  const [user, setUser] = useState(null);
  const [heroMovie, setHeroMovie] = useState(null);
  const [trending, setTrending] = useState([]);
  const [loadingHero, setLoadingHero] = useState(true);
  const [loadingTrending, setLoadingTrending] = useState(true);
  const [errorHero, setErrorHero] = useState('');
  const [errorTrending, setErrorTrending] = useState('');

  useEffect(() => {
    async function fetchData() {
      try {
        const u = await getMe();
        setUser(u);
      } catch (e) {
        // Not logged in, that's fine
      }

      try {
        const recs = await getRecommendations({ limit: 1, includeExplanations: true });
        if (recs && recs.movies && recs.movies.length > 0) {
          setHeroMovie(recs.movies[0]);
        }
      } catch (e) {
        setErrorHero('Failed to load recommendation.');
      } finally {
        setLoadingHero(false);
      }

      try {
        const trend = await getTrending(1, 6);
        if (trend && trend.items) {
          setTrending(trend.items);
        }
      } catch (e) {
        setErrorTrending('Failed to load trending movies.');
      } finally {
        setLoadingTrending(false);
      }
    }
    fetchData();
  }, [ratingVersion]); // re-fetch whenever a rating is submitted

  return (
    <div className="space-y-20">
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

      {/* Hero Section */}
      <section>
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-bold text-accent-secondary tracking-wider uppercase">
              {user ? `Good evening, ${user.username}` : 'Welcome'}
            </span>
            <span className="text-xs text-text-secondary/50">•</span>
            <span className="text-xs text-text-secondary/80 font-medium">Powered by MOVICO AI</span>
          </div>
          <h1 className="text-4xl md:text-6xl font-display text-text-primary tracking-wide uppercase leading-tight drop-shadow-md">
            What should we <span className="text-accent-gold">watch today?</span>
          </h1>
          <p className="text-text-secondary/80 text-sm md:text-base mt-2 max-w-lg">Personalized recommendations, just for you, powered by hybrid AI.</p>
        </div>

        <GlassCard className="relative overflow-hidden flex flex-col min-h-[450px] md:min-h-[500px] w-full p-0 shadow-2xl">
          {loadingHero ? (
            <div className="flex-1 bg-white/[0.03] animate-pulse flex items-center justify-center">
              <span className="text-text-secondary/60 text-sm">Loading your personalized pick...</span>
            </div>
          ) : errorHero ? (
            <div className="flex-1 bg-white/[0.03] flex items-center justify-center text-red-400/80 p-8 text-sm">
              {errorHero}
            </div>
          ) : heroMovie ? (
            <>
              {/* Widescreen Backdrop */}
              <div 
                className="absolute inset-0 bg-cover bg-center z-0"
                style={{ backgroundImage: `url(${heroMovie.backdrop_url || heroMovie.poster_url})` }}
              />
              {/* Heavy Cinematic Gradient Overlay */}
              <div className="absolute inset-0 bg-gradient-to-r from-[#0B0E14] via-[#0B0E14]/80 to-transparent z-0" />
              <div className="absolute inset-0 bg-gradient-to-t from-[#0B0E14] via-transparent to-transparent z-0" />
              
              <div className="relative z-10 p-8 md:p-14 flex flex-col justify-end flex-1 w-full md:w-2/3 h-full pb-10">
                <div className="flex items-center gap-2 mb-5">
                  <span className="bg-accent-gold text-black text-[10px] font-extrabold px-3 py-1.5 rounded-md uppercase tracking-widest shadow-lg shadow-accent-gold/20">
                    Recommended for you
                  </span>
                </div>

                <h2 className="text-4xl md:text-6xl font-display text-white mb-4 leading-none tracking-wide uppercase drop-shadow-lg">
                  {heroMovie.title}
                </h2>
                
                <div className="flex flex-wrap items-center gap-5 text-sm text-white/90 mb-6 font-medium drop-shadow-md">
                  <div className="flex items-center gap-1.5 text-rating font-bold bg-black/40 px-3 py-1 rounded-full backdrop-blur-sm border border-white/10">
                    <Star size={14} className="fill-rating" />
                    <span>{heroMovie.vote_average ? heroMovie.vote_average.toFixed(1) : 'NR'}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Calendar size={14} className="text-text-secondary" />
                    <span>{heroMovie.release_date ? heroMovie.release_date.substring(0, 4) : 'N/A'}</span>
                  </div>
                  {heroMovie.runtime && (
                    <div className="flex items-center gap-1.5">
                      <Clock size={14} className="text-text-secondary" />
                      <span>{heroMovie.runtime} min</span>
                    </div>
                  )}
                </div>

                <div className="flex flex-wrap gap-2 mb-8">
                  {heroMovie.genres && heroMovie.genres.split('|').map(g => (
                    <span key={g} className="text-xs border border-white/20 rounded-full px-4 py-1.5 bg-black/40 backdrop-blur-md text-white/90 font-medium">
                      {g}
                    </span>
                  ))}
                </div>

                <div className="flex flex-wrap gap-4">
                  <Link 
                    to="/recommendations" 
                    className="btn-gold flex items-center justify-center gap-2 py-3.5 px-8 rounded-xl text-black font-extrabold text-sm tracking-wide transition-all shadow-[0_10px_30px_rgba(232,184,75,0.25)]"
                  >
                    <Play size={18} className="fill-black" />
                    Get Recommendation
                  </Link>
                  <Link 
                    to="/browse"
                    className="flex items-center justify-center gap-2 bg-white/10 hover:bg-white/20 backdrop-blur-md border border-white/20 text-white px-8 py-3.5 rounded-xl font-bold text-sm transition-all duration-200"
                  >
                    Browse All Movies
                  </Link>
                </div>
              </div>
            </>
          ) : (
            <div className="flex-1 bg-white/[0.03] flex items-center justify-center p-8">
              <span className="text-text-secondary/60 text-sm">No recommendations available. Start rating some movies!</span>
            </div>
          )}
        </GlassCard>
      </section>

      {/* Trending Section */}
      <section>
        <div className="flex items-center justify-between mb-5">
          <h2 className="section-header">Popular Among Users</h2>
          <Link to="/trending" className="text-accent-primary hover:text-accent-primaryHover text-xs font-semibold transition-colors uppercase tracking-wider">
            View All →
          </Link>
        </div>

        {loadingTrending ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {[1,2,3,4,5,6].map(i => (
              <GlassCard key={i} className="aspect-[2/3] animate-pulse bg-white/[0.03] p-0" />
            ))}
          </div>
        ) : errorTrending ? (
          <div className="text-red-400/80 p-4 text-sm">{errorTrending}</div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-5">
            {trending.map((movie, index) => (
              <MovieCard key={movie.id} movie={movie} rank={index + 1} />
            ))}
          </div>
        )}
      </section>

      {/* User Dashboard Section */}
      {user && (
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <RatingInsights />
          <WatchlistPanel />
        </section>
      )}
    </div>
  );
}
