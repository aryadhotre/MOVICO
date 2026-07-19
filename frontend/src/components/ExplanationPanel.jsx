import React, { useEffect, useState } from 'react';
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';
import { Doughnut } from 'react-chartjs-2';
import GlassCard from './GlassCard';
import { ArrowRight, Clapperboard } from 'lucide-react';
import { getMovieById } from '../api/movies';

ChartJS.register(ArcElement, Tooltip, Legend);

export default function ExplanationPanel({ movie }) {
  const explanation = movie.explanation;
  const [sourceMovie, setSourceMovie] = useState(null);

  useEffect(() => {
    if (explanation && explanation.because_watched_id) {
      getMovieById(explanation.because_watched_id)
        .then(res => setSourceMovie(res))
        .catch(() => {});
    }
  }, [explanation]);

  if (!explanation) return null;

  // Render Popularity Fallback
  if (explanation.reason_type === 'popularity' || explanation.reason_type === 'popularity_cold_start') {
    return (
      <div className="grid grid-cols-1 gap-6">
        <GlassCard className="p-6 text-center border-accent-secondary/20">
          <h3 className="text-xl font-bold mb-3 text-text-primary">Why We Picked This</h3>
          <p className="text-accent-secondary font-medium tracking-wide">
            {explanation.message || "This movie is currently highly popular among our users."}
          </p>
        </GlassCard>
      </div>
    );
  }

  // Chart data
  const cWeight = explanation.collab_weight || 0;
  const tWeight = explanation.content_weight || 0;
  
  const chartData = {
    labels: ['Collaborative Filtering', 'Content Similarity'],
    datasets: [
      {
        data: [cWeight, tWeight],
        backgroundColor: ['#8B5CF6', '#22D3EE'],
        borderColor: ['#0B0E14', '#0B0E14'],
        borderWidth: 2,
        hoverOffset: 4
      }
    ]
  };

  const chartOptions = {
    cutout: '75%',
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (context) => ` ${context.label}: ${(context.raw * 100).toFixed(0)}%`
        }
      }
    }
  };

  const leanedMore = cWeight > tWeight ? "Collaborative Filtering (Users like you)" : "Content Similarity (Similar traits)";

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Blend Card */}
      <GlassCard className="p-6 flex flex-col items-center">
        <h3 className="text-lg font-bold mb-6 self-start text-text-primary">AI Recommendation Blend</h3>
        <div className="w-48 h-48 relative mb-6">
          <Doughnut data={chartData} options={chartOptions} />
          <div className="absolute inset-0 flex items-center justify-center flex-col">
            <span className="text-2xl font-bold text-white">AI</span>
            <span className="text-xs text-text-secondary uppercase">Model</span>
          </div>
        </div>
        <div className="flex gap-4 text-xs font-medium w-full justify-center mb-4">
          <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-[#8B5CF6]"></div> Collaborative</div>
          <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-[#22D3EE]"></div> Content</div>
        </div>
        <p className="text-sm text-text-secondary text-center px-4">
          This pick leaned more on <br/><span className="text-text-primary font-semibold">{leanedMore}</span>
        </p>
      </GlassCard>

      {/* Why We Picked This Card */}
      <GlassCard className="p-6">
        <div className="flex justify-between items-start mb-6">
          <h3 className="text-lg font-bold text-text-primary">Why We Picked This</h3>
          <span className="text-[10px] font-mono bg-white/10 px-2 py-1 rounded text-accent-secondary uppercase font-bold tracking-wider">
            {explanation.reason_type}
          </span>
        </div>

        {/* Poster Arrow Row */}
        {sourceMovie && (
          <div className="flex items-center justify-center gap-4 mb-8">
            <div className="flex flex-col items-center w-24 relative group">
              {sourceMovie.poster_url ? (
                 <img src={sourceMovie.poster_url} alt={sourceMovie.title} className="w-full aspect-[2/3] object-cover rounded-md shadow-md mb-2" />
              ) : (
                 <div className="w-full aspect-[2/3] bg-gray-800 rounded-md mb-2 flex flex-col items-center justify-center text-xs text-text-secondary p-1 text-center">No Poster</div>
              )}
              <span className="text-[10px] text-center text-text-secondary leading-tight line-clamp-2 w-full">
                Because you watched<br/><strong className="text-text-primary">{sourceMovie.title}</strong>
              </span>
            </div>
            
            <div className="flex flex-col items-center text-accent-primary px-2">
              <div className="bg-accent-primary/20 border border-accent-primary/30 px-3 py-1 rounded-full text-xs font-bold mb-2 shadow-[0_0_15px_rgba(139,92,246,0.2)]">
                {explanation.similarity_score ? (explanation.similarity_score * 100).toFixed(0) : 0}% Match
              </div>
              <ArrowRight size={24} />
            </div>

            <div className="flex flex-col items-center w-24">
              {movie.poster_url ? (
                 <img src={movie.poster_url} alt={movie.title} className="w-full aspect-[2/3] object-cover rounded-md shadow-[0_0_15px_rgba(34,211,238,0.3)] mb-2 border border-accent-secondary/50" />
              ) : (
                 <div className="w-full aspect-[2/3] bg-gray-800 rounded-md mb-2 border border-accent-secondary/50 flex flex-col items-center justify-center text-xs text-text-secondary p-1 text-center">No Poster</div>
              )}
              <span className="text-[10px] text-center text-text-secondary leading-tight line-clamp-2 w-full">
                We recommended<br/><strong className="text-text-primary">{movie.title}</strong>
              </span>
            </div>
          </div>
        )}

        {/* Feature Match Bars */}
        <div className="space-y-4 px-2">
          <MatchBar label="Genre Match" score={explanation.genre_match} />
          <MatchBar label="Cast Match" score={explanation.cast_match} />
          <MatchBar label="Tag / Vibe Match" score={explanation.tag_match} />
        </div>

        {/* Director Badge */}
        {explanation.director_match === 1.0 && (
          <div className="mt-6 flex items-center justify-center">
            <div className="flex items-center gap-2 bg-yellow-500/10 text-yellow-500 border border-yellow-500/30 px-4 py-2 rounded-lg text-sm font-semibold shadow-[0_0_15px_rgba(234,179,8,0.1)]">
              <Clapperboard size={16} />
              Same Director
            </div>
          </div>
        )}
      </GlassCard>
    </div>
  );
}

function MatchBar({ label, score = 0 }) {
  const percentage = (score * 100).toFixed(0);
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-text-secondary">{label}</span>
        <span className="text-text-primary font-medium">{percentage}%</span>
      </div>
      <div className="w-full h-1.5 bg-black/40 rounded-full overflow-hidden">
        <div 
          className="h-full bg-gradient-to-r from-accent-primary to-accent-secondary rounded-full"
          style={{ width: `${percentage}%` }}
        ></div>
      </div>
    </div>
  );
}
