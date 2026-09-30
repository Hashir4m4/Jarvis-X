import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Mic, MicOff } from 'lucide-react';

export default function VoiceWaveform({ isListening = false, isSpeaking = false, onToggleMic, onVoiceResult }) {
  const [bars, setBars] = useState(Array(14).fill(15));
  const recognitionRef = useRef(null);
  const [supported, setSupported] = useState(true);
  const [interim, setInterim] = useState('');

  // Initialize Web Speech API
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setSupported(false);
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onresult = (event) => {
      let finalTranscript = '';
      let interimTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript;
        } else {
          interimTranscript += transcript;
        }
      }

      setInterim(interimTranscript);

      if (finalTranscript.trim()) {
        setInterim('');
        if (onVoiceResult) {
          onVoiceResult(finalTranscript.trim());
        }
      }
    };

    recognition.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      if (onToggleMic) onToggleMic(false);
    };

    recognition.onend = () => {
      if (onToggleMic) onToggleMic(false);
    };

    recognitionRef.current = recognition;

    return () => {
      try { recognition.abort(); } catch { /* ignore */ }
    };
  }, [onToggleMic, onVoiceResult]);

  // Start/stop recognition when isListening changes
  useEffect(() => {
    const recognition = recognitionRef.current;
    if (!recognition) return;

    if (isListening) {
      try {
        recognition.start();
      } catch {
        // Already started
      }
    } else {
      try {
        recognition.stop();
      } catch { /* ignore */ }
      setInterim('');
    }
  }, [isListening]);

  // Animate bars when listening or speaking
  useEffect(() => {
    if (!isListening && !isSpeaking) {
      setBars(Array(14).fill(15));
      return;
    }

    const interval = setInterval(() => {
      setBars(Array.from({ length: 14 }, () => Math.floor(Math.random() * 70) + 10));
    }, 100);

    return () => clearInterval(interval);
  }, [isListening, isSpeaking]);

  const handleMicClick = useCallback(() => {
    if (!supported) {
      alert('Speech recognition is not supported in this browser. Please use Chrome or Edge.');
      return;
    }
    if (onToggleMic) onToggleMic(!isListening);
  }, [supported, isListening, onToggleMic]);

  return (
    <div className="glass-panel p-3 flex flex-col gap-2 font-mono text-xs">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button 
            onClick={handleMicClick}
            className={`w-9 h-9 rounded-full flex items-center justify-center border transition-all ${
              isListening 
                ? 'border-[#00ff9d] bg-[#00ff9d]/20 text-[#00ff9d] shadow-[0_0_15px_#00ff9d] animate-pulse' 
                : 'border-[#00f3ff]/40 bg-[#00f3ff]/10 text-[#00f3ff] hover:bg-[#00f3ff]/20'
            }`}
          >
            {isListening ? <Mic className="w-4 h-4" /> : <MicOff className="w-4 h-4" />}
          </button>
          
          <div>
            <span className="text-[10px] text-[#475569] block">VOICE MATRIX</span>
            <span className="text-white font-bold text-xs uppercase">
              {isListening ? 'LISTENING...' : (isSpeaking ? 'SPEAKING...' : 'VOICE STANDBY')}
            </span>
          </div>
        </div>

        {/* Waveform Visualizer Bars */}
        <div className="flex items-center gap-[3px] h-8 px-2">
          {bars.map((h, i) => (
            <div 
              key={i}
              className={`w-[3px] rounded-full transition-all duration-100 ${
                isListening ? 'bg-[#00ff9d] shadow-[0_0_5px_#00ff9d]' : 
                isSpeaking ? 'bg-[#ff6b00] shadow-[0_0_5px_#ff6b00]' : 'bg-[#00f3ff]/30'
              }`}
              style={{ height: `${(isListening || isSpeaking) ? h : 20}%` }}
            />
          ))}
        </div>
      </div>

      {/* Live Transcription Preview */}
      {interim && (
        <div className="mt-1 px-2 py-1.5 bg-[#00ff9d]/10 border border-[#00ff9d]/30 rounded text-[11px] text-[#00ff9d] truncate">
          🎙️ "{interim}"
        </div>
      )}

      {!supported && (
        <div className="mt-1 px-2 py-1 bg-[#ff6b00]/10 border border-[#ff6b00]/30 rounded text-[10px] text-[#ff6b00]">
          ⚠ Speech API not available. Use Chrome or Edge.
        </div>
      )}
    </div>
  );
}
