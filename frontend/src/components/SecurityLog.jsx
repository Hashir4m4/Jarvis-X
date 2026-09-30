import React from 'react';
import { ShieldCheck } from 'lucide-react';

const INITIAL_LOGS = [
  { level: 'OK', text: 'Kernel event bus initialized', time: '20:30:01' },
  { level: 'OK', text: 'AST Plugin Sandbox active', time: '20:30:02' },
  { level: 'OK', text: 'WebSocket telemetry connected', time: '20:30:03' },
  { level: 'WARN', text: 'ChromaDB fallback to SQLite memory', time: '20:30:04' },
  { level: 'OK', text: 'Jarvis OS Kernel online', time: '20:30:05' },
];

export default function SecurityLog() {
  return (
    <div className="glass-panel p-3 flex flex-col gap-2 font-mono text-xs flex-1 overflow-hidden">
      <div className="flex items-center justify-between border-b border-[#00f3ff]/20 pb-2">
        <h3 className="font-hud text-xs text-[#a855f7] flex items-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5" /> SECURITY AUDIT STREAM
        </h3>
        <span className="text-[9px] text-[#a855f7] bg-[#a855f7]/10 px-1.5 py-0.5 rounded border border-[#a855f7]/30">
          AST ENFORCED
        </span>
      </div>

      <div className="flex-1 overflow-y-auto space-y-1.5 pr-1">
        {INITIAL_LOGS.map((log, i) => (
          <div key={i} className="flex items-start gap-2 text-[11px] leading-tight">
            <span className="text-[#475569] text-[9px]">{log.time}</span>
            <span className={`font-bold text-[9px] px-1 rounded ${
              log.level === 'OK' ? 'text-[#00ff9d] bg-[#00ff9d]/10' : 'text-[#ffb700] bg-[#ffb700]/10'
            }`}>
              [{log.level}]
            </span>
            <span className="text-[#7dd3fc] truncate">{log.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
