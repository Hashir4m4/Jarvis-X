import React from 'react';
import useAppStore from '../../store/useAppStore';
import Bar from '../ui/Bar';

export default function TelemetryPanel() {
  const stats = useAppStore(state => state.stats);
  const cpu = stats.cpu || 0;
  const ram = stats.ram || 0;
  const temp = Math.round(42 + cpu * 0.3);

  return (
    <div className="flex flex-col gap-1.5 overflow-y-auto pr-0.5" style={{ fontSize: 0 }}>
      {/* Temperature Core */}
      <div className="hud-panel p-2">
        <div className="flex items-center gap-1 mb-1">
          <span className="label">[TEMP]</span>
        </div>
        <div style={{ fontFamily: 'var(--font-hud)', fontSize: '32px', fontWeight: 800, color: 'var(--cyan)', textShadow: '0 0 15px rgba(0,229,255,0.4)', lineHeight: 1 }}>
          {temp}<span style={{ fontSize: '16px', color: 'var(--text-2)' }}>°C</span>
        </div>
      </div>

      {/* RAM Section */}
      <div className="hud-panel p-2">
        <span className="label block mb-1.5">[RAM]</span>
        <div className="flex gap-1 mb-1.5">
          <div className="flex-1 hud-panel p-1 text-center">
            <span className="text-[8px] font-mono block" style={{ color: 'var(--text-2)' }}>FREE</span>
            <span className="value text-[11px]" style={{ color: 'var(--green)' }}>{(16 - ram * 0.16).toFixed(1)}</span>
            <span className="text-[7px] font-mono" style={{ color: 'var(--text-2)' }}> GB</span>
          </div>
          <div className="flex-1 hud-panel p-1 text-center">
            <span className="text-[8px] font-mono block" style={{ color: 'var(--text-2)' }}>USED</span>
            <span className="value text-[11px]" style={{ color: 'var(--red)' }}>{(ram * 0.16).toFixed(1)}</span>
            <span className="text-[7px] font-mono" style={{ color: 'var(--text-2)' }}> GB</span>
          </div>
        </div>
        <Bar label="TOTAL" value={ram} color="bar-red" />
      </div>

      {/* CPU Section */}
      <div className="hud-panel p-2">
        <span className="label block mb-1.5">[CPU]</span>
        <div className="flex justify-between text-[9px] font-mono mb-1">
          <span style={{ color: 'var(--text-2)' }}>{cpu.toFixed(0)}% &nbsp; CPU {(cpu * 0.042).toFixed(0)} MHz</span>
        </div>
        <Bar label="LOAD" value={cpu} color="bar-red" />
        <span className="text-[8px] font-mono block mt-1" style={{ color: 'var(--text-2)' }}>CPU TEMPERATURE</span>
        <div className="flex gap-2 items-center mt-0.5">
          <div className="bar-track flex-1">
            <div className="bar-fill bar-amber" style={{ width: `${temp}%` }} />
          </div>
          <span className="value text-[10px]" style={{ color: temp > 70 ? 'var(--red)' : 'var(--amber)' }}>{temp}°C</span>
        </div>
      </div>

      {/* Disk Section */}
      <div className="hud-panel p-2">
        <div className="flex justify-between items-center">
          <span className="font-mono text-[10px]" style={{ color: 'var(--cyan)' }}>{(345 - 345 * 0.37).toFixed(1)} GB FREE</span>
          <span className="font-mono text-[9px]" style={{ color: 'var(--text-2)' }}>/ 345.1 GB</span>
        </div>
        <div className="bar-track mt-1">
          <div className="bar-fill bar-cyan" style={{ width: '63%' }} />
        </div>
      </div>
    </div>
  );
}
