import React, { useState, useEffect } from 'react';
import { getHistory } from '../api/ratings';
import GlassCard from './GlassCard';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Tooltip } from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { Link } from 'react-router-dom';
import { Star } from 'lucide-react';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip);

export default function RatingInsights() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await getHistory(1, 500); // get history for insights
        setHistory(res.items || []);
      } catch (e) {
        // error handled silently
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return <GlassCard className="p-6 min-h-[400px] animate-pulse bg-white/5" />;
  }

  if (history.length === 0) {
    return (
      <GlassCard className="p-8 text-center flex flex-col items-center justify-center min-h-[400px]">
        <Star size={40} className="text-text-secondary mb-4 opacity-50" />
        <p className="text-text-primary font-semibold mb-2">No ratings yet</p>
        <p className="text-text-secondary text-sm mb-6">Start rating movies to see insights here.</p>
        <Link to="/browse" className="bg-accent-primary hover:bg-accent-primaryHover text-white px-4 py-2 rounded-lg text-sm font-semibold transition-colors">
          Find Movies
        </Link>
      </GlassCard>
    );
  }

  const totalRatings = history.length;
  const averageRating = (history.reduce((sum, item) => sum + item.rating, 0) / totalRatings).toFixed(1);
  const highest = Math.max(...history.map(item => item.rating));
  const lowest = Math.min(...history.map(item => item.rating));

  // Chart data
  const counts = {};
  for (let i = 0.5; i <= 5; i += 0.5) counts[i.toFixed(1)] = 0;
  history.forEach(item => {
    const r = item.rating.toFixed(1);
    if (counts[r] !== undefined) counts[r]++;
  });

  const chartData = {
    labels: Object.keys(counts),
    datasets: [{
      data: Object.values(counts),
      backgroundColor: '#8B5CF6',
      borderRadius: 4,
    }]
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { display: false }, ticks: { color: '#94a3b8' } },
      y: { display: false }
    }
  };

  return (
    <GlassCard className="p-6 flex flex-col min-h-[400px]">
      <div className="flex items-center justify-between mb-6 shrink-0">
        <h3 className="text-xl font-bold text-text-primary">Rating Insights</h3>
        <Link to="/ratings" className="text-sm font-semibold text-accent-primary hover:text-accent-primaryHover transition-colors">
          View History
        </Link>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6 shrink-0">
        <div className="bg-white/5 p-4 rounded-xl border border-white/10">
          <p className="text-xs text-text-secondary uppercase tracking-wider mb-1">Total Ratings</p>
          <p className="text-2xl font-bold text-white">{totalRatings}</p>
        </div>
        <div className="bg-white/5 p-4 rounded-xl border border-white/10">
          <p className="text-xs text-text-secondary uppercase tracking-wider mb-1">Average</p>
          <p className="text-2xl font-bold text-white flex items-center gap-1">
            {averageRating} <Star size={16} className="fill-rating text-rating" />
          </p>
        </div>
        <div className="bg-white/5 p-4 rounded-xl border border-white/10">
          <p className="text-xs text-text-secondary uppercase tracking-wider mb-1">Highest</p>
          <p className="text-xl font-bold text-white">{highest.toFixed(1)}</p>
        </div>
        <div className="bg-white/5 p-4 rounded-xl border border-white/10">
          <p className="text-xs text-text-secondary uppercase tracking-wider mb-1">Lowest</p>
          <p className="text-xl font-bold text-white">{lowest.toFixed(1)}</p>
        </div>
      </div>

      <div className="flex-1 min-h-[150px]">
        <Bar data={chartData} options={chartOptions} />
      </div>
    </GlassCard>
  );
}
