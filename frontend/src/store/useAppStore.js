import { create } from 'zustand';

const useAppStore = create((set) => ({
  // Connection State
  isConnected: false,
  setConnected: (status) => set({ isConnected: status }),

  // Voice & AI Operating State ('IDLE', 'LISTENING', 'TRANSCRIBING', 'THINKING', 'EXECUTING', 'SPEAKING', 'ERROR')
  voiceState: 'IDLE',
  setVoiceState: (state) => set({ voiceState: state }),

  // Hardware Telemetry
  stats: {
    cpu: null,
    ram: null,
    ramTotal: null,
    temp: null,
    swap: null,
    wifi: null,
    os: null
  },
  setStats: (newStats) => set((state) => ({ stats: { ...state.stats, ...newStats } })),

  // Active Multi-Agent State
  activeAgent: {
    agent: 'none',
    state: 'IDLE',
    step: 0,
    total_steps: 0,
    task: ''
  },
  setActiveAgent: (agentData) => set((state) => ({ activeAgent: { ...state.activeAgent, ...agentData } })),

  // Scheduled Tasks
  schedules: [],
  setSchedules: (schedules) => set({ schedules }),

  // Activity & Event Stream
  activityLogs: [],
  addActivityLog: (log) => set((state) => ({
    activityLogs: [
      ...state.activityLogs.slice(-40),
      { id: Date.now(), time: new Date().toLocaleTimeString(), ...log }
    ]
  })),

  // Dialogue & Command History
  messages: [],
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  appendStreamChunk: (chunk) => set((state) => {
    const newMessages = [...state.messages];
    const lastMessage = newMessages[newMessages.length - 1];
    
    if (lastMessage?.role === 'assistant') {
      lastMessage.content += chunk;
    } else {
      newMessages.push({ role: 'assistant', content: chunk, skill: 'core' });
    }
    
    return { messages: newMessages };
  }),
  clearMessages: () => set({ messages: [] }),

  // Input & Push-To-Talk State
  isPushToTalk: false,
  setPushToTalk: (active) => set({ isPushToTalk: active }),

  // Vault Memory Stats
  memoryStats: {
    dailyNotes: null,
    outputReports: null,
    status: 'Waiting for Sync...'
  },
  setMemoryStats: (stats) => set((state) => ({ memoryStats: { ...state.memoryStats, ...stats } })),

  // System & AI Health Status
  systemHealth: {
    status: 'offline',
    core: false,
    brain: false,
    memory: false,
    skills: 0,
    schedules: 0
  },
  setSystemHealth: (health) => set({ systemHealth: health }),

  // AI Details
  aiStatus: {
    provider: 'Unknown',
    model: 'Unknown',
    mode: 'Unknown',
    latency: null
  },
  setAiStatus: (status) => set((state) => ({ aiStatus: { ...state.aiStatus, ...status } }))
}));

export default useAppStore;
