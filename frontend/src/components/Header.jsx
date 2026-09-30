import React, { useState, useEffect } from 'react';
import { ShieldCheck, Activity, Wifi, Cpu } from 'lucide-react';
import useAppStore from '../store/useAppStore';

export default function Header() {
  const isConnected = useAppStore(state => state.isConnected);
  const voiceState = useAppStore(state => state.voiceState);
  const aiStatus = useAppStore(state => state.aiStatus);
  const [time, setTime] = useState(new Date().toLocaleTimeString());

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date().toLocaleTimeString());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const stateColors = {
    IDLE: 'text-cyan-400 bg-cyan-950/40 border-cyan-800/60',
    RUNNING: 'text-blue-400 bg-blue-950/40 border-blue-800/60 animate-pulse',
    SUCCESS: 'text-emerald-400 bg-emerald-950/40 border-emerald-800/60',
    FAILED: 'text-red-400 bg-red-950/40 border-red-800/60',
    CANCELLED: 'text-amber-400 bg-amber-950/40 border-amber-800/60',
    WAITING_FOR_CONFIRMATION: 'text-orange-400 bg-orange-950/40 border-orange-800/60 animate-pulse',
    LISTENING: 'text-amber-400 bg-amber-950/40 border-amber-800/60 animate-pulse',
    TRANSCRIBING: 'text-indigo-400 bg-indigo-950/40 border-indigo-800/60',
    THINKING: 'text-blue-400 bg-blue-950/40 border-blue-800/60 animate-pulse',
    EXECUTING: 'text-purple-400 bg-purple-950/40 border-purple-800/60',
    SPEAKING: 'text-emerald-400 bg-emerald-950/40 border-emerald-800/60',
    ERROR: 'text-red-400 bg-red-950/40 border-red-800/60'
  };

  return (
    <header className="flex items-center justify-between px-4 py-2 bg-[#05080c] border-b border-cyan-950/80 select-none">
      {/* Left: Branding & Core Identifier */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <Cpu className="text-cyan-400 animate-pulse" size={16} />
          <span className="font-mono text-sm font-black tracking-widest text-cyan-400">
            JARVIS OS
          </span>
          <span className="text-[10px] font-mono text-cyan-700 bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-900/40">
            CORE v2.0
          </span>
        </div>
      </div>

      {/* Center: Real-time Operating Voice / AI State */}
      <div className="flex items-center gap-3 font-mono">
        <div className={`flex items-center gap-2 px-3 py-1 rounded-xs border text-xs font-semibold uppercase tracking-wider transition-colors ${stateColors[voiceState] || stateColors.IDLE}`}>
          <Activity size={12} className={voiceState === 'LISTENING' || voiceState === 'THINKING' ? 'animate-spin' : ''} />
          <span>VOICE STATE: {voiceState}</span>
        </div>
      </div>

      {/* Right: AI Status, Clock & Connection Link */}
      <div className="flex items-center gap-4 font-mono text-xs">
        {/* AI Engine Status */}
        <div className="hidden md:flex flex-col items-end mr-2">
          <span className="text-[10px] text-zinc-500 uppercase font-bold tracking-wider">{aiStatus.provider} // {aiStatus.mode}</span>
          <span className="text-[11px] text-cyan-500 font-semibold">{aiStatus.model}</span>
        </div>

        <div className="text-zinc-400 font-medium tracking-wider">
          {time}
        </div>
        <div className="flex items-center gap-1.5 border-l border-cyan-950 pl-4">
          <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400 shadow-[0_0_8px_#10b981]' : 'bg-red-500'}`} />
          <span className={`text-[11px] font-bold tracking-wider uppercase ${isConnected ? 'text-emerald-400' : 'text-red-400'}`}>
            {isConnected ? 'ONLINE' : 'OFFLINE'}
          </span>
        </div>
      </div>
    </header>
  );
}
