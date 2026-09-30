import React, { useState, useEffect } from 'react';

export default function ClockPanel() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const hours = time.getHours().toString().padStart(2, '0');
  const minutes = time.getMinutes().toString().padStart(2, '0');
  const seconds = time.getSeconds().toString().padStart(2, '0');
  
  const dateStr = time.toLocaleDateString('en-US', { day: '2-digit', month: '2-digit', year: 'numeric' });
  const dayStr = time.toLocaleDateString('en-US', { weekday: 'long' });

  return (
    <div className="hud-panel p-2">
      <div 
        style={{ 
          fontFamily: 'var(--font-hud)', 
          fontSize: '42px', 
          fontWeight: 900, 
          color: 'var(--red-bright)', 
          textShadow: '0 0 25px var(--red-glow), 0 0 50px rgba(229,62,62,0.2)', 
          letterSpacing: '6px', 
          lineHeight: 1 
        }}
      >
        {hours}:<span style={{ color: 'var(--red)' }}>{minutes}</span>:<span style={{ fontSize: '24px', color: 'var(--text-1)' }}>{seconds}</span>
      </div>
      
      <div className="flex justify-between mt-1">
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-2)' }}>
          {dayStr}
        </span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-1)' }}>
          {dateStr}
        </span>
      </div>
    </div>
  );
}
