import React from 'react';
import { Bot, Cpu, Eye, Shield, Code, Mic } from 'lucide-react';

const AGENTS = [
  { id: 'kernel', name: 'OS Kernel', icon: Cpu, color: '#00f3ff', status: 'ACTIVE' },
  { id: 'planner', name: 'Planner Agent', icon: Bot, color: '#3b82f6', status: 'READY' },
  { id: 'vision', name: 'Vision Engine', icon: Eye, color: '#ff6b00', status: 'ONLINE' },
  { id: 'voice', name: 'Voice Agent', icon: Mic, color: '#00ff9d', status: 'STANDBY' },
  { id: 'coding', name: 'Coding Agent', icon: Code, color: '#ffb700', status: 'IDLE' },
  { id: 'security', name: 'Security Proxy', icon: Shield, color: '#a855f7', status: 'ENFORCING' },
];

export default function AgentPanel() {
  return (
    <div className="glass-panel p-4 flex flex-col gap-3 font-mono text-xs">
      <div className="flex items-center justify-between border-b border-[#00f3ff]/20 pb-2">
        <h3 className="font-hud text-sm text-[#00f3ff] flex items-center gap-2">
          <Bot className="w-4 h-4 text-[#00f3ff]" /> MULTI-AGENT SWARM
        </h3>
        <span className="text-[10px] text-[#7dd3fc]">6/6 ONLINE</span>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {AGENTS.map((agent) => {
          const Icon = agent.icon;
          return (
            <div 
              key={agent.id}
              className="bg-[#030712]/70 p-2.5 rounded border border-[#00f3ff]/20 flex flex-col gap-1 hover:border-[#00f3ff]/50 transition-all cursor-pointer group"
            >
              <div className="flex items-center justify-between">
                <Icon className="w-4 h-4" style={{ color: agent.color }} />
                <span 
                  className="text-[9px] px-1.5 py-0.5 rounded font-bold"
                  style={{ 
                    color: agent.color, 
                    backgroundColor: `${agent.color}15`,
                    borderColor: `${agent.color}40`,
                    borderWidth: '1px'
                  }}
                >
                  {agent.status}
                </span>
              </div>
              <span className="text-white font-bold text-xs mt-1 group-hover:text-[#00f3ff] transition-colors">
                {agent.name}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
