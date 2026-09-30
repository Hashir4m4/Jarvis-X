import React from 'react';
import { Eye, Crosshair, Camera } from 'lucide-react';

export default function VisionPreview() {
  return (
    <div className="glass-panel p-3 flex flex-col gap-2 font-mono text-xs relative overflow-hidden">
      <div className="flex items-center justify-between border-b border-[#00f3ff]/20 pb-2">
        <h3 className="font-hud text-xs text-[#ff6b00] flex items-center gap-1.5">
          <Eye className="w-3.5 h-3.5" /> VISION MATRIX FEED
        </h3>
        <span className="text-[9px] text-[#ff6b00] bg-[#ff6b00]/10 px-1.5 py-0.5 rounded border border-[#ff6b00]/30 animate-pulse">
          YOLO / VLM SCANNING
        </span>
      </div>

      {/* Simulated Holographic Viewport */}
      <div className="w-full h-32 bg-[#030712]/90 rounded border border-[#ff6b00]/30 relative flex items-center justify-center overflow-hidden group">
        {/* Grid Overlay */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(255,107,0,0.1)_0,transparent_100%)]" />
        
        {/* Animated Target Reticle */}
        <div className="w-16 h-16 rounded-full border border-[#ff6b00]/40 flex items-center justify-center animate-radar">
          <Crosshair className="w-8 h-8 text-[#ff6b00]/70" />
        </div>

        {/* Bounding Box HUD Targets */}
        <div className="absolute top-3 left-4 border border-[#00f3ff] bg-[#00f3ff]/10 px-1.5 py-0.5 text-[9px] text-[#00f3ff]">
          TARGET [01]: USER FACE (99.2%)
        </div>

        <div className="absolute bottom-3 right-4 border border-[#00ff9d] bg-[#00ff9d]/10 px-1.5 py-0.5 text-[9px] text-[#00ff9d]">
          SCREEN: DISPLAY 1 (1920x1080)
        </div>

        <button className="absolute top-2 right-2 p-1 bg-[#030712]/80 rounded border border-[#ff6b00]/40 text-[#ff6b00] hover:bg-[#ff6b00]/20 transition-all">
          <Camera className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
