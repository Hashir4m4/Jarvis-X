import React, { useState, useRef, useEffect } from 'react';
import useAppStore from '../../store/useAppStore';

export default function ChatConsole({ sendMessage }) {
  const [input, setInput] = useState('');
  const messages = useAppStore(state => state.messages);
  const aiStatus = useAppStore(state => state.aiStatus);
  const isConnected = useAppStore(state => state.isConnected);
  const chatEnd = useRef(null);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = (e) => {
    if (e) e.preventDefault();
    if (!input.trim() || !isConnected) return;
    sendMessage(input);
    setInput('');
  };

  return (
    <div className="hud-panel p-2 flex flex-col overflow-hidden" style={{ maxHeight: '200px', minHeight: '140px' }}>
      <div className="flex justify-between mb-1">
        <span className="label">Main Interface</span>
        <span className="font-mono text-[9px]" style={{ color: aiStatus === 'THINKING' ? 'var(--amber)' : aiStatus === 'SPEAKING' ? 'var(--green)' : 'var(--text-2)' }}>
          {aiStatus === 'THINKING' ? '◌ PROCESSING...' : aiStatus === 'SPEAKING' ? '◉ STREAMING' : '○ READY'}
        </span>
      </div>
      
      <div className="flex-1 overflow-y-auto space-y-1.5 pr-1 min-h-0">
        {messages.map((m, i) => {
          if (m.role === 'system') {
            return (
              <div key={i} className="text-center text-[9px] font-mono py-0.5" style={{ color: 'var(--red)' }}>
                [ {m.content} ]
              </div>
            );
          }
          
          const isUser = m.role === 'user';
          return (
            <div key={i} className={`flex gap-1.5 max-w-[90%] animate-slide-in ${isUser ? 'ml-auto flex-row-reverse' : ''}`}>
              <div className="w-4 h-4 rounded flex items-center justify-center shrink-0 text-[8px] font-mono font-bold"
                style={{ background: isUser ? 'var(--cyan-dim)' : 'var(--red-dim)', border: `1px solid ${isUser ? 'var(--cyan-border)' : 'var(--red-border)'}`, color: isUser ? 'var(--cyan)' : 'var(--red)' }}>
                {isUser ? 'U' : 'J'}
              </div>
              <div className="px-2 py-1 rounded text-[11px] leading-snug"
                style={{ background: isUser ? 'var(--cyan-dim)' : 'var(--red-dim)', border: `1px solid ${isUser ? 'var(--cyan-border)' : 'var(--red-border)'}`, color: 'var(--text-0)' }}>
                <p className="whitespace-pre-wrap" style={{ fontFamily: 'var(--font-body)' }}>{m.content}</p>
              </div>
            </div>
          );
        })}
        <div ref={chatEnd} />
      </div>
      
      <form onSubmit={handleSend} className="flex gap-1.5 mt-1.5 pt-1.5" style={{ borderTop: '1px solid var(--border)' }}>
        <input 
          value={input} 
          onChange={e => setInput(e.target.value)} 
          placeholder={isConnected ? "Enter command..." : "Connecting..."} 
          disabled={!isConnected}
          className="flex-1 px-2 py-1 rounded text-[11px] outline-none transition-colors" 
          style={{ background: 'rgba(229,62,62,0.05)', border: '1px solid var(--border)', color: 'var(--text-0)', fontFamily: 'var(--font-mono)' }}
          onFocus={e => e.target.style.borderColor = 'var(--red)'} 
          onBlur={e => e.target.style.borderColor = 'var(--border)'} 
        />
        <button 
          type="submit" 
          disabled={!isConnected || !input.trim()} 
          className="px-3 py-1 rounded text-[9px] font-mono font-bold transition-all disabled:opacity-30 cursor-pointer"
          style={{ background: 'var(--red-dim)', border: '1px solid var(--red-border)', color: 'var(--red-bright)' }}
          onMouseEnter={e => { if (!e.target.disabled) { e.target.style.background = 'var(--red)'; e.target.style.color = '#fff'; }}}
          onMouseLeave={e => { e.target.style.background = 'var(--red-dim)'; e.target.style.color = 'var(--red-bright)'; }}
        >
          SEND ►
        </button>
      </form>
    </div>
  );
}
