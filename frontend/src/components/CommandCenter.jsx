import React, { useState, useEffect } from 'react';
import { Search, X, AppWindow, Terminal, FileCode, Play, Cpu } from 'lucide-react';

const QUICK_COMMANDS = [
  { label: 'Open Application (Chrome, VSCode, Notepad)', cmd: 'open_app', icon: AppWindow, category: 'PC Control' },
  { label: 'Execute PowerShell Command', cmd: 'run_powershell', icon: Terminal, category: 'System' },
  { label: 'Run Python Script', cmd: 'run_python', icon: FileCode, category: 'Coding' },
  { label: 'Capture Screen & Analyze with VLM', cmd: 'screenshot_vlm', icon: Play, category: 'Vision' },
  { label: 'System Diagnostics & Telemetry', cmd: 'get_system_info', icon: Cpu, category: 'Diagnostics' },
];

export default function CommandCenter({ isOpen, onClose, onSelectCommand }) {
  const [search, setSearch] = useState('');

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        if (isOpen) onClose(); else onSelectCommand(null);
      }
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose, onSelectCommand]);

  if (!isOpen) return null;

  const filtered = QUICK_COMMANDS.filter(c => 
    c.label.toLowerCase().includes(search.toLowerCase()) || 
    c.category.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 bg-[#030712]/80 backdrop-blur-lg flex items-center justify-center p-4">
      <div className="glass-panel w-full max-w-xl p-6 flex flex-col gap-4 font-mono shadow-[0_0_50px_rgba(0,243,255,0.2)] animate-pulse-glow">
        
        {/* Search Header */}
        <div className="flex items-center justify-between border-b border-[#00f3ff]/30 pb-3">
          <div className="flex items-center gap-3 flex-1">
            <Search className="w-5 h-5 text-[#00f3ff]" />
            <input 
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Type a command or search action..."
              autoFocus
              className="bg-transparent text-white text-sm focus:outline-none w-full placeholder-[#475569]"
            />
          </div>
          <button onClick={onClose} className="text-[#475569] hover:text-[#00f3ff] transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Command List */}
        <div className="max-h-72 overflow-y-auto space-y-2">
          {filtered.map((item, idx) => {
            const Icon = item.icon;
            return (
              <button
                key={idx}
                onClick={() => {
                  onSelectCommand(item);
                  onClose();
                }}
                className="w-full text-left p-3 rounded bg-[#030712]/60 border border-[#00f3ff]/10 hover:border-[#00f3ff]/50 hover:bg-[#00f3ff]/10 transition-all flex items-center justify-between group"
              >
                <div className="flex items-center gap-3">
                  <Icon className="w-4 h-4 text-[#00f3ff] group-hover:scale-110 transition-transform" />
                  <span className="text-xs text-white group-hover:text-[#00f3ff] transition-colors">{item.label}</span>
                </div>
                <span className="text-[10px] text-[#7dd3fc] bg-[#00f3ff]/10 px-2 py-0.5 rounded border border-[#00f3ff]/20">
                  {item.category}
                </span>
              </button>
            );
          })}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between text-[10px] text-[#475569] border-t border-[#00f3ff]/10 pt-3">
          <span>ESC to close</span>
          <span>JARVIS OS COMMAND DISPATCH</span>
        </div>
      </div>
    </div>
  );
}
