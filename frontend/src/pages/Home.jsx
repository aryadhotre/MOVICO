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
    <div className="space-y-12">
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
          <h1 className="text-3xl font-bold text-text-primary">
            {user ? `Welcome back, ${user.username}` : 'Welcome to MOVICO'}
          </h1>
          <p className="text-text-secondary mt-1">What should we watch today?</p>
        </div>

        <GlassCard className="relative overflow-hidden flex flex-col md:flex-row min-h-[400px]">
          {loadingHero ? (
            <div className="flex-1 bg-white/5 animate-pulse flex items-center justify-center">
              <span className="text-text-secondary">Loading your personalized pick...</span>
            </div>
          ) : errorHero ? (
            <div className="flex-1 bg-white/5 flex items-center justify-center text-red-400 p-8">
              {errorHero}
            </div>
          ) : heroMovie ? (
            <>
              {/* Backdrop Background with Gradient Overlay */}
              <div 
                className="absolute inset-0 bg-cover bg-center z-0 opacity-40"
                style={{ backgroundImage: `url(${heroMovie.backdrop_url || heroMovie.poster_url})` }}
              />
              <div className="absolute inset-0 bg-gradient-to-r from-[#0B0E14] via-[#0B0E14]/80 to-transparent z-0" />
              
              <div className="relative z-10 p-10 flex flex-col justify-center flex-1 w-full md:w-1/2">
                <div className="flex items-center gap-3 mb-4">
                  <span className="bg-accent-primary text-white text-xs font-bold px-2 py-1 rounded">
                    TOP MATCH
                  </span>
                  {heroMovie.explanation && (
                    <span className="text-accent-secondary text-sm font-medium">
                      ✨ {heroMovie.explanation.message || `Because you watched ${heroMovie.explanation.because_watched_title}`}
                    </span>
                  )}
                </div>

                <h2 className="text-4xl md:text-5xl font-bold text-white mb-4 leading-tight">
                  {heroMovie.title}
                </h2>
                
                <div className="flex flex-wrap items-center gap-4 text-sm text-text-secondary mb-6">
                  <div className="flex items-center gap-1 text-rating font-medium">
                    <Star size={16} className="fill-rating" />
                    <span>{heroMovie.vote_average ? heroMovie.vote_average.toFixed(1) : 'NR'}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Calendar size={16} />
                    <span>{heroMovie.release_date ? heroMovie.release_date.substring(0, 4) : 'N/A'}</span>
                  </div>
                  {heroMovie.runtime && (
                    <div className="flex items-center gap-1">
                      <Clock size={16} />
                      <span>{heroMovie.runtime} min</span>
                    </div>
                  )}
                </div>

                <div className="flex flex-wrap gap-2 mb-8">
                  {heroMovie.genres && heroMovie.genres.split('|').map(g => (
                    <span key={g} className="text-xs border border-white/20 rounded-full px-3 py-1 bg-white/5">
                      {g}
                    </span>
                  ))}
                </div>

                <div className="flex flex-wrap gap-4">
                  <Link 
                    to={`/movies/${heroMovie.id}`} 
                    className="flex items-center gap-2 bg-accent-primary hover:bg-accent-primaryHover text-white px-6 py-3 rounded-lg font-semibold transition-colors"
                  >
                    <Play size={20} className="fill-white" />
                    Movie Details
                  </Link>
                  <Link 
                    to="/browse"
                    className="flex items-center gap-2 bg-white/10 hover:bg-white/20 text-white px-6 py-3 rounded-lg font-semibold transition-colors"
                  >
                    Browse All Movies
                  </Link>
                </div>
              </div>
            </>
          ) : (
            <div className="flex-1 bg-white/5 flex items-center justify-center p-8">
              <span className="text-text-secondary">No recommendations available. Start rating some movies!</span>
            </div>
          )}
        </GlassCard>
      </section>

      {/* Trending Section */}
      <section>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-text-primary">Trending This Week</h2>
          <Link to="/trending" className="text-accent-primary hover:text-accent-primaryHover text-sm font-semibold transition-colors">
            View All
          </Link>
        </div>

        {loadingTrending ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-6">
            {[1,2,3,4,5,6].map(i => (
              <GlassCard key={i} className="h-72 animate-pulse bg-white/5 p-0" />
            ))}
          </div>
        ) : errorTrending ? (
          <div className="text-red-400 p-4">{errorTrending}</div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-6">
            {trending.map((movie, index) => (
              <Link to={`/movies/${movie.id}`} key={movie.id} className="group block">
                <GlassCard className="h-full flex flex-col p-0 overflow-hidden group-hover:-translate-y-2 transition-transform duration-300">
                  <div className="relative aspect-[2/3] w-full bg-gray-800">
                    {movie.poster_url ? (
                      <img 
                        src={movie.poster_url} 
                        alt={movie.title} 
                        className="w-full h-full object-cover"
                        loading="lazy"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center p-4 text-center text-text-secondary">
                        No Poster
                      </div>
                    )}
                    
                    <div className="absolute top-2 left-2 bg-black/60 backdrop-blur-md text-white w-8 h-8 rounded-full flex items-center justify-center font-bold border border-white/10">
                      {index + 1}
                    </div>
                  </div>
                  
                  <div className="p-4 flex-1 flex flex-col justify-between">
                    <div>
                      <h3 className="font-semibold text-text-primary text-sm line-clamp-2 mb-1 group-hover:text-accent-primary transition-colors">
                        {movie.title}
                      </h3>
                      <p className="text-xs text-text-secondary">
                        {movie.release_date ? movie.release_date.substring(0, 4) : 'N/A'}
                      </p>
                    </div>
                    <div className="flex items-center gap-1 text-rating mt-2">
                      <Star size={12} className="fill-rating" />
                      <span className="text-xs font-semibold">{movie.vote_average ? movie.vote_average.toFixed(1) : 'NR'}</span>
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
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <RatingInsights />
          <WatchlistPanel />
        </section>
      )}
    </div>
  );
}
