import React from 'react';
import { Database, Users, Clock, ShieldCheck, Activity, Terminal } from 'lucide-react';
import useAppStore from '../store/useAppStore';

export default function BottomStatusRibbon() {
  const isConnected = useAppStore(state => state.isConnected);
  const activeAgent = useAppStore(state => state.activeAgent);
  const schedules = useAppStore(state => state.schedules);
  const memoryStats = useAppStore(state => state.memoryStats);
  const activityLogs = useAppStore(state => state.activityLogs);
  const systemHealth = useAppStore(state => state.systemHealth);

  const latestLog = activityLogs[activityLogs.length - 1]?.message || 'System nominal';

  return (
    <footer className="flex items-center justify-between px-3 py-1.5 bg-[#04070a] border-t border-cyan-950/80 font-mono text-[11px] text-zinc-400 select-none overflow-x-auto">
      {/* 1. Memory Vault */}
      <div className="flex items-center gap-1.5 shrink-0 pr-3 border-r border-cyan-950">
        <Database size={12} className="text-cyan-400" />
        <span className="text-zinc-500 uppercase">VAULT:</span>
        <span className="text-cyan-300 font-semibold">{memoryStats.status || 'UNSYNCED'}</span>
      </div>

      {/* 2. Active Multi-Agent Status */}
      <div className="flex items-center gap-1.5 shrink-0 px-3 border-r border-cyan-950">
        <Users size={12} className={activeAgent.agent !== 'none' ? 'text-indigo-400 animate-pulse' : 'text-zinc-600'} />
        <span className="text-zinc-500 uppercase">AGENTS:</span>
        <span className={`font-semibold ${activeAgent.agent !== 'none' ? 'text-indigo-300' : 'text-zinc-500'}`}>
          {activeAgent.agent !== 'none' ? `${activeAgent.agent.toUpperCase()} (${activeAgent.state})` : 'SWARM STANDBY'}
        </span>
      </div>

      {/* 3. Scheduler Tasks */}
      <div className="flex items-center gap-1.5 shrink-0 px-3 border-r border-cyan-950">
        <Clock size={12} className="text-amber-400" />
        <span className="text-zinc-500 uppercase">SCHEDULER:</span>
        <span className="text-amber-300 font-semibold">{schedules.length} ACTIVE</span>
      </div>

      {/* 4. Live Activity Log Stream */}
      <div className="flex items-center gap-1.5 shrink-0 px-3 flex-1 min-w-[200px] truncate">
        <Activity size={12} className="text-emerald-400" />
        <span className="text-zinc-500 uppercase">EVENT:</span>
        <span className="text-zinc-300 truncate">{latestLog}</span>
      </div>

      {/* 5. Core Operational Status */}
      <div className="flex items-center gap-1.5 shrink-0 pl-3">
        <ShieldCheck size={12} className={systemHealth.core ? 'text-emerald-400' : 'text-red-400'} />
        <span className="text-zinc-500 uppercase">CORE STATUS:</span>
        <span className={systemHealth.core ? 'text-emerald-400 font-bold' : 'text-red-400 font-bold'}>
          {systemHealth.core ? 'ONLINE' : 'DEGRADED / OFFLINE'}
        </span>
      </div>
    </footer>
  );
}
