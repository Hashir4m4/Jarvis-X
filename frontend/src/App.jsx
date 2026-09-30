import React, { useEffect, useRef } from 'react';
import useWebSocket from './hooks/useWebSocket';
import useAppStore from './store/useAppStore';

import Header from './components/Header';
import TelemetryPanel from './components/TelemetryPanel';
import Jarvis3DCore from './components/3d/Jarvis3DCore';
import CommandDeck from './components/CommandDeck';
import VoiceCommandConsole from './components/VoiceCommandConsole';
import BottomStatusRibbon from './components/BottomStatusRibbon';

import './index.css';

export default function App() {
  const { sendMessage, triggerPushToTalk, stopPushToTalk, cancelOperation } = useWebSocket();
  const voiceState = useAppStore(state => state.voiceState);
  const isSpaceDown = useRef(false);

  // Global Keyboard Shortcuts (Space = Push-to-Talk, Escape = Cancel)
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Escape cancels ongoing operation regardless of focus
      if (e.key === 'Escape') {
        e.preventDefault();
        cancelOperation();
        return;
      }

      // Space triggers PTT only if not actively typing in an input or textarea
      if (e.code === 'Space') {
        if (e.repeat) return; // Prevent duplicate triggers while held down
        const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
        if (activeTag !== 'input' && activeTag !== 'textarea') {
          e.preventDefault();
          isSpaceDown.current = true;
          triggerPushToTalk();
        }
      }
    };

    const handleKeyUp = (e) => {
      if (e.code === 'Space') {
        if (isSpaceDown.current) {
          isSpaceDown.current = false;
          stopPushToTalk();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [triggerPushToTalk, stopPushToTalk, cancelOperation]);

  return (
    <div className="w-screen h-screen flex flex-col bg-[#03060a] text-zinc-100 overflow-hidden font-mono select-none antialiased">
      {/* 1. Header (System Info, Clock, Voice Status, Link) */}
      <Header />

      {/* 2. Main Center Grid (3 Columns: Telemetry, 3D AI Core, Command Deck) */}
      <div className="flex-1 grid grid-cols-12 gap-2 p-2 min-h-0">
        {/* Left Column: System Telemetry (3 cols) */}
        <div className="col-span-3 h-full">
          <TelemetryPanel />
        </div>

        {/* Center Column: 3D Holographic AI Core (6 cols) */}
        <div className="col-span-6 h-full flex flex-col bg-[#05080c] border border-cyan-950/70 rounded-sm relative overflow-hidden shadow-2xl">
          <div className="absolute top-2 left-3 z-10 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
            <span className="text-[11px] font-bold text-cyan-400 uppercase tracking-widest">
              NEURAL REACTOR CORE // 3D MATRIX
            </span>
          </div>

          <div className="flex-1 w-full h-full relative">
            <Jarvis3DCore status={voiceState} />
          </div>

          {/* Real-time State Banner inside Core */}
          <div className="absolute bottom-2 inset-x-3 flex justify-between items-center text-[10px] text-zinc-500 bg-black/60 backdrop-blur-xs px-3 py-1 rounded border border-cyan-950/80">
            <span className="text-cyan-400 font-semibold tracking-wider uppercase">
              STATUS: {voiceState}
            </span>
            <span className="text-zinc-500">
              PRESS [SPACE] FOR PTT / [ESC] TO CANCEL
            </span>
          </div>
        </div>

        {/* Right Column: Command Deck (3 cols) */}
        <div className="col-span-3 h-full">
          <CommandDeck
            onExecuteCommand={sendMessage}
            isExecuting={voiceState === 'THINKING' || voiceState === 'EXECUTING'}
          />
        </div>
      </div>

      {/* 3. Lower Middle Band: Voice & Command Execution Console (Height: 260px) */}
      <div className="h-[250px] px-2 pb-1 shrink-0">
        <VoiceCommandConsole
          onSendMessage={sendMessage}
          onTriggerPTT={triggerPushToTalk}
          onCancelOperation={cancelOperation}
        />
      </div>

      {/* 4. Bottom Status Ribbon (Memory, Agents, Tasks, Activity, Status) */}
      <BottomStatusRibbon />
    </div>
  );
}
