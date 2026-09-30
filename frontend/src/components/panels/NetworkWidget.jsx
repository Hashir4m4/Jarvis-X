import React from 'react';

export default function NetworkWidget() {
  return (
    <div className="hud-panel p-2">
      <span className="label block mb-1">UPLOAD / DOWNLOAD</span>
      <div className="font-mono text-[9px]">
        <div className="flex justify-between">
          <span style={{ color: 'var(--text-2)' }}>▲ UPLOAD</span>
          <span style={{ color: 'var(--red)' }}>25.3 KB/s</span>
        </div>
        <div className="flex justify-between mt-0.5">
          <span style={{ color: 'var(--text-2)' }}>▼ DOWNLOAD</span>
          <span style={{ color: 'var(--cyan)' }}>68.5 KB/s</span>
        </div>
      </div>
      <div className="bar-track mt-1">
        <div className="bar-fill bar-red" style={{ width: '30%' }} />
      </div>
      <div className="bar-track mt-1">
        <div className="bar-fill bar-cyan" style={{ width: '65%' }} />
      </div>
    </div>
  );
}
