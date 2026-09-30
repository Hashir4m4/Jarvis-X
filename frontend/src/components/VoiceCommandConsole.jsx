import React, { useState, useRef, useEffect } from 'react';
import { Terminal, Mic, MicOff, Send, XCircle, ArrowRight } from 'lucide-react';
import useAppStore from '../store/useAppStore';

export default function VoiceCommandConsole({ onSendMessage, onTriggerPTT, onCancelOperation }) {
  const [inputVal, setInputVal] = useState('');
  const messages = useAppStore(state => state.messages);
  const voiceState = useAppStore(state => state.voiceState);
  const isConnected = useAppStore(state => state.isConnected);
  const consoleBottomRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom of console stream
  useEffect(() => {
    if (consoleBottomRef.current) {
      consoleBottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, voiceState]);

  // Focus input automatically
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!inputVal.trim()) return;
    onSendMessage(inputVal.trim());
    setInputVal('');
  };

  const isBusy = voiceState === 'THINKING' || voiceState === 'EXECUTING' || voiceState === 'TRANSCRIBING';

  return (
    <div className="flex flex-col h-full bg-[#05080c] border border-cyan-950/80 rounded-sm font-mono text-zinc-300 shadow-2xl overflow-hidden">
      {/* Console Top Ribbon */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-[#080d14] border-b border-cyan-900/40 text-xs">
        <div className="flex items-center gap-2">
          <Terminal size={13} className="text-cyan-400" />
          <span className="font-bold tracking-wider text-cyan-400 uppercase">
            VOICE & COMMAND EXECUTION CONSOLE
          </span>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-zinc-500">
          <span>SHORTCUTS: <kbd className="text-cyan-400 bg-black/60 px-1 py-0.5 rounded border border-zinc-800">SPACE</kbd> = TALK | <kbd className="text-cyan-400 bg-black/60 px-1 py-0.5 rounded border border-zinc-800">ESC</kbd> = CANCEL</span>
        </div>
      </div>

      {/* Response Display Area (High Information Density) */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3 scrollbar-thin scrollbar-thumb-cyan-950 scrollbar-track-transparent">
        {messages.map((msg, index) => {
          const isUser = msg.role === 'user';
          return (
            <div
              key={index}
              className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}
            >
              <div className="flex items-center gap-1.5 text-[10px] text-zinc-500 mb-0.5 uppercase tracking-wider">
                <span>{isUser ? 'USER COMMAND' : 'JARVIS OS RESPONSE'}</span>
                {msg.skill && (
                  <span className="text-cyan-600 bg-cyan-950/60 px-1 rounded border border-cyan-900/40">
                    [{msg.skill}]
                  </span>
                )}
                {msg.execution_time_ms && (
                  <span className="text-zinc-600">
                    {msg.execution_time_ms}ms
                  </span>
                )}
              </div>
              <div
                className={`max-w-[95%] p-2.5 rounded-xs text-xs font-mono leading-relaxed whitespace-pre-wrap ${
                  isUser
                    ? 'bg-cyan-950/30 border border-cyan-800/50 text-cyan-200'
                    : 'bg-[#090e17] border border-cyan-950/80 text-zinc-200 shadow-md'
                }`}
              >
                {msg.content}
              </div>
            </div>
          );
        })}

        {/* Live Status indicator while thinking/executing */}
        {isBusy && (
          <div className="flex items-center gap-2 text-xs font-mono text-cyan-400 animate-pulse bg-cyan-950/20 border border-cyan-900/40 p-2 rounded-xs w-fit">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
            <span>JARVIS CORE EXECUTING [{voiceState}]...</span>
          </div>
        )}

        <div ref={consoleBottomRef} />
      </div>

      {/* Input Prompt Band with Blinking Cursor & Push-to-Talk Button */}
      <form onSubmit={handleSubmit} className="flex items-center gap-2 p-2 bg-[#070c14] border-t border-cyan-950/80">
        <div className="flex items-center gap-2 text-cyan-400 font-mono font-bold text-sm pl-2 shrink-0">
          <ArrowRight size={14} className="animate-pulse" />
          <span>&gt;</span>
        </div>

        <input
          ref={inputRef}
          type="text"
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          placeholder={voiceState === 'LISTENING' ? "Listening to microphone... [RELEASE SPACE TO STOP]" : "Enter command or prompt (e.g. 'Plan today', 'Morning brief', 'Show system status')..."}
          disabled={!isConnected}
          className="flex-1 bg-transparent text-xs font-mono text-cyan-100 placeholder-zinc-600 focus:outline-none focus:ring-0 disabled:opacity-40"
        />

        {/* Push-To-Talk Toggle Button */}
        <button
          type="button"
          onClick={onTriggerPTT}
          title="Push to Talk (or hold SPACE)"
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-xs text-xs font-mono font-semibold border transition-all ${
            voiceState === 'LISTENING'
              ? 'bg-red-950/80 border-red-500 text-red-300 animate-pulse'
              : 'bg-cyan-950/40 border-cyan-800/60 text-cyan-400 hover:bg-cyan-900/40'
          }`}
        >
          {voiceState === 'LISTENING' ? <MicOff size={13} /> : <Mic size={13} />}
          <span className="text-[11px]">{voiceState === 'LISTENING' ? 'LISTENING' : 'PTT [SPACE]'}</span>
        </button>

        {/* Cancel Button */}
        {isBusy && (
          <button
            type="button"
            onClick={onCancelOperation}
            title="Cancel Operation (ESC)"
            className="flex items-center gap-1 px-2 py-1.5 bg-red-950/60 border border-red-800/60 text-red-400 hover:bg-red-900/60 rounded-xs text-xs"
          >
            <XCircle size={13} />
            <span className="text-[10px]">CANCEL [ESC]</span>
          </button>
        )}

        {/* Send Button */}
        <button
          type="submit"
          disabled={!inputVal.trim() || !isConnected}
          className="p-1.5 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-30 text-black font-bold rounded-xs transition-colors"
        >
          <Send size={13} />
        </button>
      </form>
    </div>
  );
}
