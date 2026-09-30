import React, { useRef, useEffect } from 'react';
import { Send, Terminal, Bot, User, Sparkles } from 'lucide-react';

export default function ChatPanel({ messages = [], input = '', setInput, onSendMessage, isConnected }) {
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="glass-panel p-4 flex flex-col h-full overflow-hidden font-mono">
      {/* Panel Header */}
      <div className="flex items-center justify-between border-b border-[#00f3ff]/20 pb-3 mb-3">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-[#00f3ff]" />
          <h2 className="font-hud text-sm text-[#00f3ff]">JARVIS CORE INTERFACE</h2>
        </div>
        <span className="text-[10px] text-[#7dd3fc] bg-[#00f3ff]/10 px-2 py-0.5 rounded border border-[#00f3ff]/30">
          STREAMING BUS: ACTIVE
        </span>
      </div>

      {/* Messages Stream Area */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-[#475569] gap-3">
            <Sparkles className="w-8 h-8 text-[#00f3ff]/40 animate-pulse" />
            <p className="text-xs uppercase tracking-widest">AWAITING DIRECTIVE OR VOICE COMMAND...</p>
          </div>
        ) : (
          messages.map((msg, idx) => {
            const isUser = msg.role === 'user';
            const isSystem = msg.role === 'system';

            if (isSystem) {
              return (
                <div key={idx} className="text-center my-2 text-[11px] text-[#00f3ff] bg-[#00f3ff]/5 border border-[#00f3ff]/20 py-1 px-3 rounded">
                  [SYSTEM PROTOCOL]: {msg.content}
                </div>
              );
            }

            return (
              <div 
                key={idx}
                className={`flex gap-3 max-w-[88%] ${isUser ? 'ml-auto flex-row-reverse' : ''}`}
              >
                {/* Avatar Badge */}
                <div className={`w-7 h-7 rounded flex items-center justify-center shrink-0 border ${
                  isUser 
                    ? 'bg-[#3b82f6]/20 border-[#3b82f6] text-[#3b82f6]' 
                    : 'bg-[#ff6b00]/20 border-[#ff6b00] text-[#ff6b00]'
                }`}>
                  {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                </div>

                {/* Message Body */}
                <div className={`p-3 rounded text-xs leading-relaxed border backdrop-blur-md ${
                  isUser 
                    ? 'bg-[#3b82f6]/10 border-[#3b82f6]/40 text-white rounded-tr-none' 
                    : 'bg-[#071026]/80 border-[#00f3ff]/30 text-[#f0f9ff] rounded-tl-none shadow-[0_4px_20px_rgba(0,0,0,0.4)]'
                }`}>
                  <div className="flex items-center justify-between text-[10px] text-[#7dd3fc] mb-1 font-bold">
                    <span>{isUser ? 'OPERATOR' : 'JARVIS AI'}</span>
                  </div>

                  <div className="whitespace-pre-wrap font-sans">
                    {msg.content}
                  </div>
                </div>
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Form */}
      <form onSubmit={onSendMessage} className="mt-3 flex gap-2 pt-3 border-t border-[#00f3ff]/20">
        <input 
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={isConnected ? "Execute command or type message..." : "Connecting to Jarvis OS..."}
          disabled={!isConnected}
          className="flex-1 bg-[#030712]/90 border border-[#00f3ff]/30 text-white placeholder-[#475569] px-4 py-2.5 rounded text-xs focus:outline-none focus:border-[#00f3ff] focus:ring-1 focus:ring-[#00f3ff] transition-all font-mono"
        />
        <button 
          type="submit"
          disabled={!isConnected || !input.trim()}
          className="btn-hologram px-4 py-2.5 text-xs disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Send className="w-4 h-4" />
          <span className="hidden sm:inline">SEND</span>
        </button>
      </form>
    </div>
  );
}
