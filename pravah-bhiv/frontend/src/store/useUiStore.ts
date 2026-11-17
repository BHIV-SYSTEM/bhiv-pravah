import { create } from 'zustand';

export interface NotificationItem {
  id: string;
  timestamp: string;
  message: string;
  type: 'info' | 'warn' | 'error' | 'success';
  read: boolean;
}

interface UiState {
  sidebarOpen: boolean;
  commandPaletteOpen: boolean;
  notifications: NotificationItem[];
  activeTraceId: string | null;
  activeExecutionId: string | null;
  
  // Actions
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  toggleCommandPalette: () => void;
  setCommandPaletteOpen: (open: boolean) => void;
  addNotification: (message: string, type: NotificationItem['type']) => void;
  markAllNotificationsRead: () => void;
  clearNotifications: () => void;
  setActiveTraceId: (traceId: string | null) => void;
  setActiveExecutionId: (executionId: string | null) => void;
}

export const useUiStore = create<UiState>((set) => ({
  sidebarOpen: true,
  commandPaletteOpen: false,
  notifications: [
    {
      id: 'init-notification',
      timestamp: new Date().toISOString(),
      message: 'PRAVAH Console initialized successfully.',
      type: 'success',
      read: false,
    }
  ],
  activeTraceId: null,
  activeExecutionId: null,

  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  
  toggleCommandPalette: () => set((state) => ({ commandPaletteOpen: !state.commandPaletteOpen })),
  setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),
  
  addNotification: (message, type) => set((state) => {
    const newNotif: NotificationItem = {
      id: `notif-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date().toISOString(),
      message,
      type,
      read: false,
    };
    return { notifications: [newNotif, ...state.notifications].slice(0, 50) };
  }),
  
  markAllNotificationsRead: () => set((state) => ({
    notifications: state.notifications.map(n => ({ ...n, read: true }))
  })),
  
  clearNotifications: () => set({ notifications: [] }),
  
  setActiveTraceId: (traceId) => set({ activeTraceId: traceId }),
  setActiveExecutionId: (executionId) => set({ activeExecutionId: executionId }),
}));
