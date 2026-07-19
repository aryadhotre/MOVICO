import React, { useState, useEffect } from 'react';
import { getRecommendations } from '../api/recommendations';
import GlassCard from '../components/GlassCard';
import ExplanationPanel from '../components/ExplanationPanel';
import { Sparkles, Star, Play } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function Recommendations() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      try {
        const res = await getRecommendations({ limit: 5, includeExplanations: true });
        setData(res);
      } catch (e) {
        setError("Failed to fetch personalized recommendations.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-text-primary flex items-center gap-3">
            <Sparkles className="text-accent-primary" /> 
            For You
          </h1>
          <p className="text-text-secondary mt-2">Personalized picks powered by AI.</p>
        </div>
        
        {/* Recommendation Type Badge */}
        {data && data.recommendation_type && (
          <div className="bg-accent-primary/10 border border-accent-primary/20 px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-semibold text-accent-primary shadow-[0_0_15px_rgba(139,92,246,0.15)]">
            <span>Type:</span>
            <span className="text-white uppercase tracking-wider text-xs bg-accent-primary/40 px-2 py-1 rounded">
              {data.recommendation_type.replace(/_/g, ' ')}
            </span>
          </div>
        )}
      </div>

      {loading ? (
        <div className="space-y-12">
          {[1,2].map(i => (
            <GlassCard key={i} className="h-96 animate-pulse bg-white/5" />
          ))}
        </div>
      ) : error ? (
        <GlassCard className="p-8 text-center text-red-400 font-medium">
          {error}
        </GlassCard>
      ) : (
        <div className="space-y-16">
          {data.movies.map((movie, index) => (
            <div key={movie.id} className="space-y-6">
              {/* Movie Header Card */}
              <GlassCard className="p-6 flex flex-col md:flex-row gap-6 relative overflow-hidden group">
                <div className="w-32 md:w-48 shrink-0 relative z-10">
                  {movie.poster_url ? (
                    <img src={movie.poster_url} alt={movie.title} className="w-full aspect-[2/3] object-cover rounded-lg shadow-lg border border-white/10 group-hover:border-accent-primary/50 transition-colors" />
                  ) : (
                    <div className="w-full aspect-[2/3] bg-gray-800 rounded-lg flex items-center justify-center text-text-secondary text-sm text-center p-4 border border-white/10">No Poster</div>
                  )}
                  <div className="absolute -top-3 -left-3 bg-accent-primary text-white w-10 h-10 rounded-full flex items-center justify-center font-black text-xl shadow-[0_0_15px_rgba(139,92,246,0.5)]">
                    {index + 1}
                  </div>
                </div>
                
                <div className="flex-1 relative z-10 flex flex-col justify-center">
                  <h2 className="text-3xl font-bold text-white mb-2">{movie.title}</h2>
                  <div className="flex flex-wrap items-center gap-4 text-sm text-text-secondary mb-4">
                    <div className="flex items-center gap-1 text-rating font-medium">
                      <Star size={16} className="fill-rating" />
                      <span>{movie.vote_average ? movie.vote_average.toFixed(1) : 'NR'}</span>
                    </div>
                    {movie.release_date && <span>{movie.release_date.substring(0, 4)}</span>}
                    {movie.runtime && <span>{movie.runtime} min</span>}
                  </div>
                  <div className="flex flex-wrap gap-2 mb-4">
                    {movie.genres && movie.genres.split('|').map(g => (
                      <span key={g} className="text-xs border border-white/20 rounded-full px-3 py-1 bg-white/5 text-text-secondary">
                        {g}
                      </span>
                    ))}
                  </div>
                  <p className="text-text-secondary text-sm line-clamp-3 mb-6 max-w-3xl">
                    {movie.overview}
                  </p>
                  
                  <div className="mt-auto self-start">
                    <Link to={`/movies/${movie.id}`} className="flex items-center gap-2 bg-white/10 hover:bg-white/20 text-white px-5 py-2 rounded-lg text-sm font-semibold transition-colors">
                      <Play size={16} className="fill-white" />
                      View Details
                    </Link>
                  </div>
                </div>

                {/* Subtle Backdrop underlay */}
                {movie.backdrop_url && (
                  <>
                    <div 
                      className="absolute inset-0 bg-cover bg-center z-0 opacity-[0.03] group-hover:opacity-[0.08] transition-opacity duration-500"
                      style={{ backgroundImage: `url(${movie.backdrop_url})` }}
                    />
                    <div className="absolute inset-0 bg-gradient-to-r from-[#0B0E14] via-[#0B0E14]/90 to-[#0B0E14]/60 z-0" />
                  </>
                )}
              </GlassCard>

              {/* Explainability Panel */}
              <ExplanationPanel movie={movie} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
