import React from 'react';
import { Cpu, HardDrive, Thermometer, Wifi, Activity, Server, ActivitySquare } from 'lucide-react';
import useAppStore from '../store/useAppStore';

export default function TelemetryPanel() {
  const stats = useAppStore(state => state.stats);
  const systemHealth = useAppStore(state => state.systemHealth);

  const cpuPercent = stats.cpu !== null ? Math.min(100, Math.max(0, stats.cpu)) : 0;
  const ramPercent = stats.ram !== null ? Math.min(100, Math.max(0, stats.ram)) : 0;
  const temp = stats.temp !== null ? Math.round(stats.temp) : null;
  const swapPercent = stats.swap !== null ? Math.min(100, Math.max(0, stats.swap)) : null;

  return (
    <div className="flex flex-col h-full bg-[#070b12] border border-cyan-950/60 rounded-sm p-3 shadow-inner font-mono text-zinc-300">
      <div className="flex items-center justify-between border-b border-cyan-900/40 pb-2 mb-2">
        <div className="flex items-center gap-2">
          <Activity size={14} className="text-cyan-400" />
          <span className="text-xs font-bold tracking-wider text-cyan-400 uppercase">
            SYSTEM TELEMETRY
          </span>
        </div>
        <span className="text-[10px] text-cyan-600 tracking-wider">
          LIVE HOST SENSORS
        </span>
      </div>

      <div className="space-y-2.5 overflow-y-auto pr-1 flex-1">
        {/* CPU Utilization */}
        <div className="bg-black/30 border border-cyan-950 p-2 rounded-xs">
          <div className="flex justify-between items-center text-xs mb-1">
            <span className="flex items-center gap-1.5 text-cyan-300">
              <Cpu size={12} /> CPU LOAD
            </span>
            <span className={`font-bold ${cpuPercent > 80 ? 'text-red-400' : (cpuPercent > 50 ? 'text-amber-400' : 'text-cyan-400')}`}>
              {cpuPercent}%
            </span>
          </div>
          <div className="w-full bg-zinc-900 h-1.5 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-300 ${cpuPercent > 80 ? 'bg-red-500' : (cpuPercent > 50 ? 'bg-amber-400' : 'bg-cyan-400')}`}
              style={{ width: `${cpuPercent}%` }}
            />
          </div>
        </div>

        {/* RAM Usage */}
        <div className="bg-black/30 border border-cyan-950 p-2 rounded-xs">
          <div className="flex justify-between items-center text-xs mb-1">
            <span className="flex items-center gap-1.5 text-blue-300">
              <HardDrive size={12} /> RAM UTILIZATION
            </span>
            <span className="text-blue-400 font-bold">
              {ramPercent}% ({((ramPercent / 100) * (stats.ramTotal || 16)).toFixed(1)} GB)
            </span>
          </div>
          <div className="w-full bg-zinc-900 h-1.5 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-400 transition-all duration-300"
              style={{ width: `${ramPercent}%` }}
            />
          </div>
        </div>

        {/* Temperature & Swap */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="bg-black/30 border border-cyan-950 p-2 rounded-xs">
            <div className="flex items-center gap-1 text-zinc-400 text-[11px] mb-0.5">
              <Thermometer size={12} className="text-amber-400" /> CORE TEMP
            </div>
            <div className="text-sm font-bold text-amber-400">
              {temp !== null ? `~${temp}°C` : 'N/A'}
            </div>
          </div>
          <div className="bg-black/30 border border-cyan-950 p-2 rounded-xs">
            <div className="flex items-center gap-1 text-zinc-400 text-[11px] mb-0.5">
              <Server size={12} className="text-purple-400" /> SWAP MEM
            </div>
            <div className="text-sm font-bold text-purple-400">
              {swapPercent !== null ? `${swapPercent}%` : 'N/A'}
            </div>
          </div>
        </div>

        {/* Host & Network State */}
        <div className="bg-black/30 border border-cyan-950 p-2 rounded-xs space-y-1 text-xs">
          <div className="flex justify-between text-[11px]">
            <span className="text-zinc-500">HOST OS</span>
            <span className="text-zinc-300 font-medium">{stats.os || 'UNKNOWN'}</span>
          </div>
          <div className="flex justify-between text-[11px]">
            <span className="text-zinc-500">NETWORK ADAPTER</span>
            <span className={`font-medium flex items-center gap-1 ${stats.wifi === 'Connected' ? 'text-emerald-400' : 'text-red-400'}`}>
              <Wifi size={10} /> {stats.wifi || 'N/A'}
            </span>
          </div>
        </div>

        {/* Subsystem Diagnostics */}
        <div className="bg-black/30 border border-cyan-950 p-2 rounded-xs space-y-2 mt-2">
          <div className="flex items-center gap-1.5 border-b border-cyan-900/40 pb-1 mb-1">
            <ActivitySquare size={12} className="text-indigo-400" />
            <span className="text-[10px] text-indigo-400 font-bold tracking-wider">SUBSYSTEM DIAGNOSTICS</span>
          </div>
          <div className="flex justify-between text-[11px]">
            <span className="text-zinc-500">BRAIN (LLM ROUTER)</span>
            <span className={systemHealth.brain ? 'text-emerald-400 font-bold' : 'text-red-400 font-bold'}>
              {systemHealth.brain ? 'ONLINE' : 'UNAVAILABLE'}
            </span>
          </div>
          <div className="flex justify-between text-[11px]">
            <span className="text-zinc-500">MEMORY (CHROMA)</span>
            <span className={systemHealth.memory ? 'text-emerald-400 font-bold' : 'text-red-400 font-bold'}>
              {systemHealth.memory ? 'ONLINE' : 'UNAVAILABLE'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
