import React from 'react';
import useAppStore from '../../store/useAppStore';

export default function AgentMonitor() {
  const agents = useAppStore(state => state.agents);

  return (
    <div className="hud-panel p-2">
      <span className="label block mb-1.5">Active Agents</span>
      {agents.map(a => (
        <div key={a.name} className="flex items-center gap-1.5 py-0.5">
          <div 
            className="w-1.5 h-1.5 rounded-full" 
            style={{
              background: a.status ? 'var(--green)' : 'var(--text-2)',
              boxShadow: a.status ? '0 0 6px var(--green)' : 'none'
            }}
          />
          <span 
            className="text-[9px] font-mono" 
            style={{ color: a.status ? 'var(--text-0)' : 'var(--text-2)' }}
          >
            {a.name}
          </span>
        </div>
      ))}
    </div>
  );
}
