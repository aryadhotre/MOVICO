import React from 'react';
import RatingInsights from '../components/RatingInsights';

export default function Ratings() {
  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-text-primary">My Ratings</h1>
        <p className="text-text-secondary mt-1">Your rating history and personalized insights.</p>
      </div>
      <div className="grid grid-cols-1">
        <RatingInsights />
      </div>
      {/* In a real app we'd add the full paginated list below */}
    </div>
  );
}
