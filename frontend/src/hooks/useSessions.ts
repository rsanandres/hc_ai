'use client';

import { useState, useEffect, useCallback } from 'react';
import { createSession as createSessionApi, getSessionMessages } from '@/services/agentApi';
import { SessionMetadata } from '@/types';

// Helper to generate a UUID-like string
function generateSessionId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

// Generate ephemeral user ID (no persistence)
function generateEphemeralUserId(): string {
  return `guest_${generateSessionId().slice(0, 8)}`;
}

/**
 * Simplified session hook for MVP - creates new session on each page load
 */
export function useSessions() {
  // Initialize with empty strings to avoid hydration mismatch
  const [userId, setUserId] = useState<string>('');
  const [activeSessionId, setActiveSessionId] = useState<string>('');
  const [activeSession, setActiveSession] = useState<SessionMetadata | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isClient, setIsClient] = useState(false);

  // Create new session on mount (client-side only)
  useEffect(() => {
    setIsClient(true);

    // Generate user ID on client only to avoid hydration mismatch
    const ephemeralUserId = generateEphemeralUserId();
    setUserId(ephemeralUserId);

    const initSession = async () => {
      setIsLoading(true);
      setError(null);

      try {
        // Create session via API (DynamoDB)
        const newSession = await createSessionApi(ephemeralUserId, { name: 'New Chat' });
        console.log('[useSessions] Created new session:', newSession.session_id);
        setActiveSessionId(newSession.session_id);
        setActiveSession(newSession);
      } catch (err) {
        console.error('[useSessions] Failed to create session via API, using local fallback');
        // Fallback: use local session ID if API fails
        const localSessionId = generateSessionId();
        setActiveSessionId(localSessionId);
        setActiveSession({
          session_id: localSessionId,
          user_id: ephemeralUserId,
          name: 'New Chat',
          created_at: new Date().toISOString(),
          last_activity: new Date().toISOString(),
          message_count: 0,
        });
      } finally {
        setIsLoading(false);
      }
    };

    initSession();
  }, []);

  const loadSessionMessages = useCallback(async (sessionId: string, limit: number = 50) => {
    try {
      const messages = await getSessionMessages(sessionId, limit);
      return messages;
    } catch (err) {
      console.error('[useSessions] Failed to load messages:', err);
      return [];
    }
  }, []);

  return {
    // Session state
    activeSessionId,
    activeSession,
    isLoading,
    error,
    isClient,
    userId,

    // Simplified API - no multi-session management needed
    loadSessionMessages,

    // Legacy compatibility stubs (no-op for MVP)
    sessions: activeSession ? [activeSession] : [],
    isLoggedIn: false,
    createNewSession: async () => activeSession,
    switchSession: () => { },
    updateSession: async () => activeSession,
    removeSession: async () => { },
    checkSessionLimit: async () => false,
    maxSessions: 1,
    loadSessions: async () => { },
    login: () => { },
    saveGuestMessage: () => { },
    clearGuestSession: () => { },
  };
}
