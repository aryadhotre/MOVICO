import React from 'react';
import { Link } from 'react-router-dom';
import { Star } from 'lucide-react';
import GlassCard from './GlassCard';

export default function MovieCard({ movie, rank = null, matchPct = null }) {
  return (
    <Link to={`/movies/${movie.id}`} className="group block h-full w-full">
      <GlassCard className="h-full flex flex-col p-0 overflow-hidden group-hover:-translate-y-2 group-hover:shadow-[0_10px_30px_rgba(232,184,75,0.15)] transition-all duration-300">
        <div className="relative aspect-[2/3] w-full bg-[#0B0E14] overflow-hidden flex-1">
          {movie.poster_url ? (
            <img 
              src={movie.poster_url} 
              alt={movie.title} 
              className="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" 
              loading="lazy" 
            />
          ) : (
             <div className="absolute inset-0 w-full h-full flex items-center justify-center text-text-secondary text-xs text-center p-4">No Poster</div>
          )}
          
          {/* Heavy gradient at the bottom for text readability */}
          <div className="absolute inset-0 bg-gradient-to-t from-[#0B0E14] via-[#0B0E14]/50 to-transparent opacity-90 transition-opacity" />
          
          {rank && (
            <div className="absolute top-3 left-3 w-8 h-8 rounded-lg bg-gradient-to-br from-accent-gold/90 to-accent-goldHover/90 backdrop-blur-md text-black flex items-center justify-center font-bold text-sm border border-accent-gold/20 shadow-lg">
              {rank}
            </div>
          )}
          
          {matchPct !== null && (
            <div className="absolute top-3 right-3 badge-match shadow-lg bg-[#0B0E14]/80 backdrop-blur-md">
              {matchPct}% Match
            </div>
          )}
          
          {/* Text content pinned to bottom directly on image */}
          <div className="absolute inset-x-0 bottom-0 p-4 flex flex-col gap-1.5">
            <h3 className="font-display uppercase tracking-wide text-white text-lg leading-tight line-clamp-2 drop-shadow-md group-hover:text-accent-gold transition-colors">
              {movie.title}
            </h3>
            <div className="flex items-center justify-between text-[11px] text-white/80 font-medium">
              <span>{movie.release_date ? movie.release_date.substring(0, 4) : ''}</span>
              {movie.vote_average > 0 && (
                <div className="flex items-center gap-1 text-rating drop-shadow-sm font-bold">
                  <Star size={12} className="fill-rating" />
                  {movie.vote_average.toFixed(1)}
                </div>
              )}
            </div>
          </div>
        </div>
      </GlassCard>
    </Link>
  );
}
