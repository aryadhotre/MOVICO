import React from 'react';

export default function GlassCard({ children, className = '', ...props }) {
  return (
    <div 
      className={`bg-white/[0.04] backdrop-blur-xl border border-white/[0.07] rounded-2xl hover:border-white/[0.12] hover:shadow-[0_0_20px_rgba(139,92,246,0.15)] transition-all duration-300 ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
