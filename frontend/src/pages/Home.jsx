import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getTrending } from '../api/movies';
import { getRecommendations } from '../api/recommendations';
import { getMe } from '../api/auth';
import GlassCard from '../components/GlassCard';
import RatingInsights from '../components/RatingInsights';
import WatchlistPanel from '../components/WatchlistPanel';
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
    <div className="space-y-10">
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
        <div className="mb-5">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium text-accent-secondary tracking-wide">
              {user ? `Good evening, ${user.username}!` : ''}
            </span>
            <span className="text-xs text-text-secondary/50">•</span>
            <span className="text-xs text-text-secondary/60">Deep Recommendations powered by MOVICO AI</span>
          </div>
          <h1 className="text-3xl font-bold text-text-primary tracking-tight">
            What should we <span className="bg-gradient-to-r from-accent-primary to-accent-primaryHover bg-clip-text text-transparent">watch today?</span>
          </h1>
          <p className="text-text-secondary/70 text-sm mt-1">Personalized recommendations, just for you, powered by hybrid AI.</p>
        </div>

        <GlassCard className="relative overflow-hidden flex flex-col md:flex-row min-h-[360px]">
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
              {/* Backdrop Background with Gradient Overlay */}
              <div 
                className="absolute inset-0 bg-cover bg-center z-0 opacity-30"
                style={{ backgroundImage: `url(${heroMovie.backdrop_url || heroMovie.poster_url})` }}
              />
              <div className="absolute inset-0 bg-gradient-to-r from-[#0B0E14] via-[#0B0E14]/85 to-transparent z-0" />
              
              <div className="relative z-10 p-8 md:p-10 flex flex-col justify-center flex-1 w-full md:w-1/2">
                <div className="flex items-center gap-2 mb-4">
                  <span className="bg-gradient-to-r from-accent-primary to-accent-primaryHover text-white text-[10px] font-bold px-2.5 py-1 rounded-md uppercase tracking-wider">
                    Recommended for you
                  </span>
                </div>

                <h2 className="text-3xl md:text-4xl font-bold text-white mb-4 leading-tight tracking-tight">
                  {heroMovie.title}
                </h2>
                
                <div className="flex flex-wrap items-center gap-4 text-sm text-text-secondary/80 mb-5">
                  <div className="flex items-center gap-1 text-rating font-semibold">
                    <Star size={14} className="fill-rating" />
                    <span>{heroMovie.vote_average ? heroMovie.vote_average.toFixed(1) : 'NR'}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Calendar size={14} />
                    <span>{heroMovie.release_date ? heroMovie.release_date.substring(0, 4) : 'N/A'}</span>
                  </div>
                  {heroMovie.runtime && (
                    <div className="flex items-center gap-1">
                      <Clock size={14} />
                      <span>{heroMovie.runtime} min</span>
                    </div>
                  )}
                </div>

                <div className="flex flex-wrap gap-2 mb-6">
                  {heroMovie.genres && heroMovie.genres.split('|').map(g => (
                    <span key={g} className="text-[11px] border border-white/[0.12] rounded-full px-3 py-1 bg-white/[0.04] text-text-secondary/90">
                      {g}
                    </span>
                  ))}
                </div>

                <div className="flex flex-wrap gap-3">
                  <Link 
                    to="/recommendations" 
                    className="btn-gradient flex items-center gap-2 text-white px-5 py-2.5 rounded-xl font-semibold text-sm"
                  >
                    <Play size={16} className="fill-white" />
                    Get Recommendation
                  </Link>
                  <Link 
                    to="/browse"
                    className="flex items-center gap-2 bg-white/[0.06] hover:bg-white/[0.1] border border-white/[0.08] text-white px-5 py-2.5 rounded-xl font-semibold text-sm transition-all duration-200"
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
          <h2 className="section-header">Trending This Week</h2>
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
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {trending.map((movie, index) => (
              <Link to={`/movies/${movie.id}`} key={movie.id} className="group block">
                <GlassCard className="h-full flex flex-col p-0 overflow-hidden group-hover:-translate-y-1 transition-transform duration-300">
                  <div className="relative aspect-[2/3] w-full bg-[#161B26] rounded-t-2xl overflow-hidden">
                    {movie.poster_url ? (
                      <img 
                        src={movie.poster_url} 
                        alt={movie.title} 
                        className="w-full h-full object-cover"
                        loading="lazy"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center p-3 text-center">
                        <span className="text-text-secondary/40 text-xs">{movie.title}</span>
                      </div>
                    )}
                    
                    {/* Rank badge */}
                    <div className="absolute top-2 left-2 w-7 h-7 rounded-lg bg-gradient-to-br from-accent-primary/80 to-accent-primaryHover/80 backdrop-blur-md text-white flex items-center justify-center font-bold text-xs border border-white/20">
                      {index + 1}
                    </div>
                  </div>
                  
                  <div className="p-3 flex-1 flex flex-col justify-between">
                    <div>
                      <h3 className="font-semibold text-text-primary text-[13px] line-clamp-2 mb-0.5 group-hover:text-accent-primary transition-colors leading-tight">
                        {movie.title}
                      </h3>
                      <p className="text-[11px] text-text-secondary/60">
                        {movie.release_date ? movie.release_date.substring(0, 4) : ''}
                      </p>
                    </div>
                    <div className="flex items-center gap-1 text-rating mt-1.5">
                      <Star size={11} className="fill-rating" />
                      <span className="text-[11px] font-semibold">{movie.vote_average ? movie.vote_average.toFixed(1) : 'NR'}</span>
                    </div>
                  </div>
                </GlassCard>
              </Link>
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
