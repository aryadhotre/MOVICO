import React from 'react';

export default function Logo({ className = '' }) {
  return (
    <div className={`flex items-center gap-[1px] font-display font-bold tracking-widest text-text-primary select-none ${className}`}>
      <span>M</span>
      <span className="flex items-center justify-center -mx-[2px]">
        <svg 
          viewBox="0 0 100 100" 
          className="h-[0.7em] w-[0.7em] text-accent-gold" 
          fill="none" 
          stroke="currentColor" 
          strokeWidth="6"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          {/* Outer ring */}
          <circle cx="50" cy="50" r="45" />
          {/* Inner ring */}
          <circle cx="50" cy="50" r="18" />
          {/* Aperture blades */}
          <line x1="50" y1="32" x2="25" y2="10" />
          <line x1="68" y1="50" x2="90" y2="25" />
          <line x1="50" y1="68" x2="75" y2="90" />
          <line x1="32" y1="50" x2="10" y2="75" />
          <line x1="40" y1="35" x2="15" y2="45" />
          <line x1="60" y1="65" x2="85" y2="55" />
        </svg>
      </span>
      <span>VICO</span>
    </div>
  );
}
