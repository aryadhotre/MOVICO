import React from 'react';

export default function GlassCard({ children, className = '', ...props }) {
  return (
    <div 
      className={`bg-white/5 backdrop-blur-md border border-white/10 rounded-2xl hover:shadow-[0_0_15px_rgba(139,92,246,0.3)] transition-shadow duration-300 ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
