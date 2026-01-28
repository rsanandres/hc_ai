'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  getSessions,
  getSessionCount,
  createSession as createSessionApi,
  updateSessionMetadata,
  deleteSession,
  getSessionMessages,
} from '@/services/agentApi';
import { SessionMetadata, SessionCreateRequest } from '@/types';
import { useUser } from './useUser';

const ACTIVE_SESSION_KEY = 'atlas_active_session_id';
const MAX_SESSIONS = 20;

export function useSessions() {
  const { userId, isClient, login } = useUser();
  const [sessions, setSessions] = useState<SessionMetadata[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load active session from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(ACTIVE_SESSION_KEY);
    if (stored) {
      setActiveSessionId(stored);
    }
  }, []);

  const checkSessionLimit = useCallback(async (): Promise<boolean> => {
    if (!userId) return false;

    try {
      const count = await getSessionCount(userId);
      return count.count >= MAX_SESSIONS;
    } catch {
      return false;
    }
  }, [userId]);

  const loadSessions = useCallback(async () => {
    if (!userId) {
      console.log('[useSessions] No userId, skipping session load');
      return;
    }

    console.log('[useSessions] Loading sessions for user:', userId);
    setIsLoading(true);
    setError(null);
    try {
      // Check service health before attempting to load sessions
      try {
        const healthUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/retrieval/rerank/health`;
        const healthController = new AbortController();
        const healthTimeout = setTimeout(() => healthController.abort(), 3000);

        const healthResponse = await fetch(healthUrl, {
          signal: healthController.signal,
        });

        clearTimeout(healthTimeout);

        if (!healthResponse.ok) {
          throw new Error(`Service health check failed: ${healthResponse.status}`);
        }
      } catch (healthError) {
        const errorMsg = 'Reranker service is unavailable. Please ensure the backend service is running.';
        console.error('[useSessions] Service health check failed:', {
          error: healthError instanceof Error ? healthError.message : String(healthError),
          stack: healthError instanceof Error ? healthError.stack : undefined,
        });
        setError(errorMsg);
        setIsLoading(false);
        return;
      }

      const response = await getSessions(userId);
      console.log('[useSessions] Loaded sessions:', response?.sessions?.length || 0, response?.sessions);
      const sessionList = response?.sessions || [];
      setSessions(sessionList);

      // If no active session, either use first existing or create new one
      const storedSessionId = localStorage.getItem(ACTIVE_SESSION_KEY);
      if (storedSessionId && sessionList.some(s => s.session_id === storedSessionId)) {
        // Use stored session if it still exists
        console.log('[useSessions] Using stored session:', storedSessionId);
        setActiveSessionId(storedSessionId);
      } else if (sessionList.length > 0) {
        // Use first session if available (list is already sorted by backend)
        const firstSession = sessionList[0];
        console.log('[useSessions] Using recent session:', firstSession.session_id);
        setActiveSessionId(firstSession.session_id);
        localStorage.setItem(ACTIVE_SESSION_KEY, firstSession.session_id);
      } else {
        // Only create new session if list is empty
        console.log('[useSessions] No sessions found, creating new one');
        try {
          const newSession = await createNewSession();
          if (newSession) {
            setActiveSessionId(newSession.session_id);
            localStorage.setItem(ACTIVE_SESSION_KEY, newSession.session_id);
          }
        } catch (err) {
          console.error('[useSessions] Failed to create initial session:', err);
        }
      }
    } catch (err) {
      console.error('[useSessions] Error loading sessions:', err);
      setError(err instanceof Error ? err.message : 'Failed to load sessions');
      // On error, try to create a session anyway
      try {
        const atLimit = await checkSessionLimit();
        if (!atLimit) {
          const newSession = await createSessionApi(userId);
          console.log('[useSessions] Created fallback session:', newSession.session_id);
          setSessions([newSession]);
          setActiveSessionId(newSession.session_id);
          localStorage.setItem(ACTIVE_SESSION_KEY, newSession.session_id);
        }
      } catch (createErr) {
        console.error('[useSessions] Failed to create fallback session:', createErr);
      }
    } finally {
      setIsLoading(false);
    }
  }, [userId, checkSessionLimit]);

  // Fetch sessions when userId is available
  useEffect(() => {
    if (userId && isClient) {
      loadSessions();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, isClient]);

  const createNewSession = useCallback(async (metadata?: Partial<SessionCreateRequest>): Promise<SessionMetadata | null> => {
    if (!userId) return null;

    try {
      // Check limit first
      const atLimit = await checkSessionLimit();
      if (atLimit) {
        throw new Error('SESSION_LIMIT_EXCEEDED');
      }

      const newSession = await createSessionApi(userId, metadata);
      setSessions(prev => [newSession, ...prev]);
      setActiveSessionId(newSession.session_id);
      localStorage.setItem(ACTIVE_SESSION_KEY, newSession.session_id);
      return newSession;
    } catch (err) {
      if (err instanceof Error && err.message === 'SESSION_LIMIT_EXCEEDED') {
        throw err;
      }
      setError(err instanceof Error ? err.message : 'Failed to create session');
      return null;
    }
  }, [userId, checkSessionLimit]);


  const switchSession = useCallback((sessionId: string) => {
    setActiveSessionId(sessionId);
    localStorage.setItem(ACTIVE_SESSION_KEY, sessionId);
  }, []);

  const updateSession = useCallback(async (sessionId: string, updates: { name?: string; description?: string; tags?: string[] }) => {
    try {
      const updated = await updateSessionMetadata(sessionId, updates);
      setSessions(prev => prev.map(s => s.session_id === sessionId ? updated : s));
      return updated;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update session');
      throw err;
    }
  }, []);

  const removeSession = useCallback(async (sessionId: string) => {
    try {
      await deleteSession(sessionId);
      setSessions(prev => prev.filter(s => s.session_id !== sessionId));

      // If deleted session was active, switch to first available or create new
      if (sessionId === activeSessionId) {
        const remaining = sessions.filter(s => s.session_id !== sessionId);
        if (remaining.length > 0) {
          switchSession(remaining[0].session_id);
        } else {
          setActiveSessionId('');
          localStorage.removeItem(ACTIVE_SESSION_KEY);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete session');
      throw err;
    }
  }, [activeSessionId, sessions, switchSession]);

  const loadSessionMessages = useCallback(async (sessionId: string, limit: number = 50) => {
    try {
      const messages = await getSessionMessages(sessionId, limit);
      return messages;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load messages');
      return [];
    }
  }, []);

  const activeSession = sessions.find(s => s.session_id === activeSessionId);

  return {
    sessions,
    activeSessionId,
    activeSession,
    isLoading,
    error,
    loadSessions,
    createNewSession,
    switchSession,
    updateSession,
    removeSession,
    loadSessionMessages,
    checkSessionLimit,
    maxSessions: MAX_SESSIONS,
    userId,
    login,
  };
}
