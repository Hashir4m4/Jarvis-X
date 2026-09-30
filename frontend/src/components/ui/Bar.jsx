import React from 'react';

export default function Bar({ label, value, max = 100, color = 'bar-red', right }) {
  const percentage = Math.min(100, (value / max) * 100);
  
  return (
    <div className="mb-1.5">
      <div className="flex justify-between mb-0.5">
        <span className="label" style={{ fontSize: '8px' }}>{label}</span>
        <span className="value" style={{ fontSize: '10px' }}>
          {right || `${typeof value === 'number' ? value.toFixed(1) : value}%`}
        </span>
      </div>
      <div className="bar-track">
        <div className={`bar-fill ${color}`} style={{ width: `${percentage}%` }} />
      </div>
    </div>
  );
}
