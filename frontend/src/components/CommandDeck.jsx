import React from 'react';
import { Play, Sparkles, Terminal, Activity, Calendar, Shield, Inbox, BarChart2 } from 'lucide-react';

export default function CommandDeck({ onExecuteCommand, isExecuting = false }) {
  const commands = [
    {
      id: 'morning_brief',
      label: 'MORNING BRIEF',
      time: '07:00',
      cmd: 'Give me my morning brief',
      icon: Sparkles,
      color: 'border-cyan-500/40 text-cyan-400 hover:bg-cyan-500/10'
    },
    {
      id: 'plan_today',
      label: 'PLAN TODAY',
      time: '09:00',
      cmd: "Plan today's priorities",
      icon: Calendar,
      color: 'border-blue-500/40 text-blue-400 hover:bg-blue-500/10'
    },
    {
      id: 'metrics_pull',
      label: 'METRICS PULL',
      time: '14:00',
      cmd: 'Pull metrics report',
      icon: BarChart2,
      color: 'border-emerald-500/40 text-emerald-400 hover:bg-emerald-500/10'
    },
    {
      id: 'close_day',
      label: 'CLOSE THE DAY',
      time: '19:00',
      cmd: 'Close the day',
      icon: Shield,
      color: 'border-purple-500/40 text-purple-400 hover:bg-purple-500/10'
    },
    {
      id: 'inbox',
      label: 'INBOX SCAN',
      time: 'ON-DEMAND',
      cmd: 'Check inbox',
      icon: Inbox,
      color: 'border-sky-500/40 text-sky-400 hover:bg-sky-500/10'
    },
    {
      id: 'trends',
      label: 'TREND SCAN',
      time: 'ANALYTICS',
      cmd: 'What changed today?',
      icon: Activity,
      color: 'border-amber-500/40 text-amber-400 hover:bg-amber-500/10'
    },
    {
      id: 'code_agent',
      label: 'MULTI-AGENT CODE',
      time: 'AGENT',
      cmd: 'Build a Python script to analyze CSV dataset',
      icon: Terminal,
      color: 'border-indigo-500/40 text-indigo-400 hover:bg-indigo-500/10'
    },
    {
      id: 'system_diag',
      label: 'SYSTEM DIAGNOSTICS',
      time: 'HARDWARE',
      cmd: 'Show my system status.',
      icon: Play,
      color: 'border-teal-500/40 text-teal-400 hover:bg-teal-500/10'
    }
  ];

  return (
    <div className="flex flex-col h-full bg-[#070b12] border border-cyan-950/60 rounded-sm p-3 shadow-inner">
      <div className="flex items-center justify-between border-b border-cyan-900/40 pb-2 mb-2">
        <div className="flex items-center gap-2">
          <Terminal size={14} className="text-cyan-400" />
          <span className="text-xs font-mono font-bold tracking-wider text-cyan-400 uppercase">
            COMMAND DECK
          </span>
        </div>
        <span className="text-[10px] font-mono text-cyan-600 tracking-wider">
          SKILLS ACTIVE
        </span>
      </div>

      <div className="grid grid-cols-1 gap-1.5 overflow-y-auto pr-1 flex-1">
        {commands.map((c) => {
          const Icon = c.icon;
          return (
            <button
              key={c.id}
              disabled={isExecuting}
              onClick={() => onExecuteCommand(c.cmd)}
              className={`group flex items-center justify-between p-2 rounded-xs border text-left font-mono transition-all duration-150 ${c.color} disabled:opacity-40 disabled:cursor-not-allowed`}
            >
              <div className="flex items-center gap-2 min-w-0">
                <Icon size={13} className="shrink-0 group-hover:scale-110 transition-transform" />
                <span className="text-xs font-semibold tracking-wide truncate">
                  {c.label}
                </span>
              </div>
              <span className="text-[10px] text-zinc-500 shrink-0 font-medium px-1.5 py-0.5 rounded bg-black/40 border border-zinc-800">
                {c.time}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
