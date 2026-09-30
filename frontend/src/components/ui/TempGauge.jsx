import React from 'react';

export default function TempGauge({ label, value, color = '#e53e3e', size = 60 }) {
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;
  
  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle 
            cx={size/2} 
            cy={size/2} 
            r={radius} 
            fill="none" 
            stroke="rgba(229,62,62,0.08)" 
            strokeWidth={3}
          />
          <circle 
            cx={size/2} 
            cy={size/2} 
            r={radius} 
            fill="none" 
            stroke={color} 
            strokeWidth={3}
            strokeDasharray={circumference} 
            strokeDashoffset={offset} 
            strokeLinecap="round"
            style={{ 
              transition: 'stroke-dashoffset 0.5s ease', 
              filter: `drop-shadow(0 0 6px ${color})` 
            }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="value" style={{ fontSize: '14px', fontWeight: 800 }}>
            {Math.round(value)}
            <span style={{ fontSize: '8px', color: 'var(--text-2)' }}>°C</span>
          </span>
        </div>
      </div>
      <span className="label mt-0.5" style={{ fontSize: '7px' }}>{label}</span>
    </div>
  );
}
