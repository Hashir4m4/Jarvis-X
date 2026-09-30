import React from 'react';

export default function SecurityLog() {
  const logs = [
    { t: 'OK', m: 'Kernel online' },
    { t: 'OK', m: 'AST sandbox' },
    { t: 'WARN', m: 'ChromaDB fallback' },
    { t: 'OK', m: 'Agents ready' }
  ];

  return (
    <div className="hud-panel p-2 flex-1 overflow-hidden">
      <span className="label block mb-1">Security</span>
      {logs.map((l, i) => (
        <div key={i} className="flex gap-1.5 text-[9px] font-mono py-0.5 animate-slide-in" style={{ animationDelay: `${i * 0.1}s` }}>
          <span style={{ color: l.t === 'OK' ? 'var(--green)' : 'var(--amber)', fontWeight: 700 }}>
            [{l.t}]
          </span>
          <span style={{ color: 'var(--text-1)' }}>{l.m}</span>
        </div>
      ))}
    </div>
  );
}
