import { useEffect, useRef, useCallback } from 'react';
import useAppStore from '../store/useAppStore';

const WS_URL =
  (typeof window !== 'undefined' && (window.__JARVIS_CONFIG__?.wsUrl || window.__JARVIS_WS_URL__)) ||
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_WS_URL) ||
  'ws://localhost:8000/ws/chat';

export default function useWebSocket() {
  const ws = useRef(null);

  const setConnected = useAppStore(state => state.setConnected);
  const setVoiceState = useAppStore(state => state.setVoiceState);
  const setStats = useAppStore(state => state.setStats);
  const setSystemHealth = useAppStore(state => state.setSystemHealth);
  const setAiStatus = useAppStore(state => state.setAiStatus);
  const setMemoryStats = useAppStore(state => state.setMemoryStats);
  const setActiveAgent = useAppStore(state => state.setActiveAgent);
  const setSchedules = useAppStore(state => state.setSchedules);
  const addActivityLog = useAppStore(state => state.addActivityLog);
  const addMessage = useAppStore(state => state.addMessage);
  const appendStreamChunk = useAppStore(state => state.appendStreamChunk);

  useEffect(() => {
    let reconnectTimer;

    const connect = () => {
      ws.current = new WebSocket(WS_URL);

      ws.current.onopen = async () => {
        setConnected(true);
        addActivityLog({ message: 'WebSocket Link Established // Core Online', level: 'info' });
        
        try {
          const res = await fetch(WS_URL.replace('ws://', 'http://').replace('/ws/chat', '/health'));
          const healthData = await res.json();
          setSystemHealth(healthData);
          setAiStatus({
            provider: healthData.provider || 'Unknown',
            model: healthData.model || 'Unknown',
            mode: healthData.mode?.value || healthData.mode || 'Unknown',
            latency: null
          });
          if (healthData.memory_stats) {
            setMemoryStats(healthData.memory_stats);
          }
        } catch (e) {
          console.error("Failed to fetch initial health state", e);
        }
      };

      ws.current.onmessage = (e) => {
        try {
          const payload = JSON.parse(e.data);
          const type = payload.type;
          const data = payload.data || payload;

          if (type === 'system_stats' || type === 'telemetry') {
            setStats(data);
          } else if (type === 'voice_state') {
            setVoiceState(data.state || 'IDLE');
          } else if (type === 'agent_status') {
            setActiveAgent(data);
            addActivityLog({ message: `Agent [${data.agent?.toUpperCase()}] -> ${data.state}`, level: 'info' });
          } else if (type === 'schedule_updated') {
            if (data.schedules) setSchedules(data.schedules);
          } else if (type === 'scheduled_task_executed') {
            addActivityLog({ message: `Scheduled Run: ${data.task_id} (${data.status})`, level: 'success' });
          } else if (type === 'chat_stream') {
            setVoiceState('SPEAKING');
            appendStreamChunk(data.chunk);
          } else if (type === 'chat_complete') {
            setVoiceState('IDLE');
            addMessage(data);
            addActivityLog({ message: `Executed: ${data.skill || 'query'} (${data.execution_time_ms || 0}ms)`, level: 'success' });
          } else if (type === 'chat_message') {
            addMessage(data);
          } else if (type === 'operation_cancelled') {
            setVoiceState('IDLE');
            addActivityLog({ message: 'Active task cancelled (ESC key trigger)', level: 'warning' });
          } else if (type === 'chat_error') {
            setVoiceState('ERROR');
            addActivityLog({ message: `Execution Error: ${data.message}`, level: 'error' });
          }
        } catch (error) {
          console.error("WebSocket message parse error:", error);
        }
      };

      ws.current.onclose = () => {
        setConnected(false);
        setVoiceState('IDLE');
        reconnectTimer = setTimeout(connect, 3000);
      };

      ws.current.onerror = (err) => {
        console.error("WebSocket error:", err);
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimer);
      if (ws.current) {
        ws.current.close();
      }
    };
  }, []);

  const sendMessage = useCallback((message) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      setVoiceState('THINKING');
      ws.current.send(JSON.stringify({ message }));
    }
  }, [setVoiceState]);

  const triggerPushToTalk = useCallback(() => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      setVoiceState('LISTENING');
      ws.current.send(JSON.stringify({ action: 'ptt' }));
    }
  }, [setVoiceState]);

  const stopPushToTalk = useCallback(() => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ action: 'stop_ptt' }));
    }
  }, []);

  const cancelOperation = useCallback(() => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ action: 'cancel' }));
      setVoiceState('IDLE');
    }
  }, [setVoiceState]);

  return { sendMessage, triggerPushToTalk, stopPushToTalk, cancelOperation };
}
