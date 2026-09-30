import React, { useState, useEffect } from 'react';
import useAppStore from '../../store/useAppStore';

function Waveform({ active }) {
  const [bars, setBars] = useState(Array(24).fill(8));
  
  useEffect(() => { 
    if (!active) {
      setBars(Array(24).fill(6));
      return;
    } 
    const id = setInterval(() => {
      setBars(Array.from({ length: 24 }, () => Math.random() * 85 + 10));
    }, 70); 
    
    return () => clearInterval(id); 
  }, [active]);
  
  return (
    <div className="flex items-end gap-[1.5px] h-5">
      {bars.map((h, i) => (
        <div 
          key={i} 
          className="flex-1 rounded-sm transition-all duration-75" 
          style={{ 
            height: `${active ? h : 8}%`, 
            background: active ? 'var(--red)' : 'var(--text-2)', 
            boxShadow: active ? '0 0 3px var(--red-glow)' : 'none', 
            opacity: active ? 0.85 : 0.25 
          }}
        />
      ))}
    </div>
  );
}

export default function VoiceMatrix() {
  const isMicActive = useAppStore(state => state.isMicActive);
  const setMicActive = useAppStore(state => state.setMicActive);

  return (
    <div className="hud-panel p-2">
      <div className="flex justify-between items-center mb-1">
        <span className="label">Voice</span>
        <button 
          onClick={() => setMicActive(!isMicActive)} 
          className="text-[8px] font-mono px-1.5 py-0.5 rounded transition-all cursor-pointer"
          style={{ 
            background: isMicActive ? 'var(--red)' : 'var(--red-dim)', 
            border: '1px solid var(--red-border)', 
            color: isMicActive ? '#fff' : 'var(--red)', 
            boxShadow: isMicActive ? '0 0 10px var(--red-glow)' : 'none' 
          }}
        >
          {isMicActive ? '■ STOP' : '● MIC'}
        </button>
      </div>
      <Waveform active={isMicActive} />
    </div>
  );
}
