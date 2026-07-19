import React from 'react';

export default function GlassCard({ children, className = '', ...props }) {
  return (
    <div 
      className={`bg-[#0B0E14]/70 backdrop-blur-2xl border border-white/10 rounded-2xl hover:border-white/[0.15] hover:shadow-[0_0_25px_rgba(232,184,75,0.1)] transition-all duration-300 ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
