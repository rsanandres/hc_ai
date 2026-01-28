'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { Message } from '@/types';
import { streamAgent, StreamEvent } from '@/services/streamAgent';
import { useSessions } from './useSessions';
import { useUser } from './useUser';

// Streaming state for real-time updates (debug mode)
export interface StreamingState {
  isStreaming: boolean;
  currentStatus: string;
  toolCalls: string[];
  researcherOutput: string;
  validatorOutput: string;
  validationResult?: string;
}

interface SessionTurn {
  turn_ts: string;
  role: string;
  text: string;
  meta?: {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    sources?: any[];
    tool_calls?: string[];
    researcher_output?: string;
    validator_output?: string;
    validation_result?: string;
  };
}

const initialStreamingState: StreamingState = {
  isStreaming: false,
  currentStatus: '',
  toolCalls: [],
  researcherOutput: '',
  validatorOutput: '',
  validationResult: undefined,
};

export function useChat(sessionId?: string) {
  const { userId } = useUser();
  const { activeSessionId, loadSessionMessages, updateSession, createNewSession } = useSessions();
  const effectiveSessionId = sessionId || activeSessionId;

  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [messageCount, setMessageCount] = useState<number>(0);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);

  // Streaming state for debug mode
  const [streamingState, setStreamingState] = useState<StreamingState>(initialStreamingState);
  const streamingToolsRef = useRef<string[]>([]);
  const ignoreNextLoadRef = useRef<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const stopGeneration = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsLoading(false);
      setStreamingState(prev => ({ ...prev, isStreaming: false, currentStatus: 'Stopped by user' }));
    }
  }, []);

  const loadMessagesForSession = useCallback(async (sid: string) => {
    if (!sid) {
      console.log('[useChat] No session ID provided, skipping message load');
      return;
    }

    // Skip load if we just created this session in this hook
    if (ignoreNextLoadRef.current === sid) {
      console.log('[useChat] Skipping message load for just-created session:', sid);
      ignoreNextLoadRef.current = null;
      return;
    }

    console.log('[useChat] Loading messages for session:', sid);
    setIsLoadingMessages(true);
    try {
      const sessionMessages = await loadSessionMessages(sid, 50);
      console.log('[useChat] Loaded session messages:', sessionMessages.length, sessionMessages);

      // Convert session turns to Message format
      const convertedMessages: Message[] = sessionMessages
        .sort((a: SessionTurn, b: SessionTurn) => {
          // Sort by turn_ts (oldest first)
          return (a.turn_ts || '').localeCompare(b.turn_ts || '');
        })
        .map((turn: SessionTurn) => ({
          id: turn.turn_ts || uuidv4(),
          role: turn.role === 'user' ? 'user' : 'assistant',
          content: turn.text || '',
          timestamp: new Date(turn.turn_ts || Date.now()),
          sources: turn.meta?.sources,
          toolCalls: turn.meta?.tool_calls,
          researcherOutput: turn.meta?.researcher_output,
          validatorOutput: turn.meta?.validator_output,
          validationResult: turn.meta?.validation_result,
        }));

      console.log('[useChat] Converted messages:', convertedMessages.length, convertedMessages);
      setMessages(convertedMessages);
      setMessageCount(convertedMessages.filter(m => m.role === 'user').length);
    } catch (err) {
      console.error('[useChat] Failed to load messages:', err);
    } finally {
      setIsLoadingMessages(false);
    }
  }, [loadSessionMessages]);

  // Load messages when session changes
  useEffect(() => {
    if (effectiveSessionId) {
      loadMessagesForSession(effectiveSessionId);
    } else {
      setMessages([]);
      setMessageCount(0);
    }
  }, [effectiveSessionId, loadMessagesForSession]);

  // Reset streaming state helper
  const resetStreamingState = useCallback(() => {
    streamingToolsRef.current = [];
    setStreamingState(initialStreamingState);
  }, []);

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoading) return;

    // Check agent service health before sending message
    try {
      const healthUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/agent/health`;
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
      const errorMsg = 'Agent service is unavailable. Please ensure the backend service is running.';
      console.error('[useChat] Service health check failed:', {
        error: healthError instanceof Error ? healthError.message : String(healthError),
        stack: healthError instanceof Error ? healthError.stack : undefined,
      });
      setError(errorMsg);
      return;
    }

    // If no session, create one first
    let sessionToUse = effectiveSessionId;
    if (!sessionToUse && userId) {
      try {
        const newSession = await createNewSession();
        if (newSession) {
          sessionToUse = newSession.session_id;
          // IMPORTANT: Set this ref to prevent the useEffect from wiping our local optimistic message
          // when the activeSessionId updates and triggers loadMessagesForSession
          ignoreNextLoadRef.current = sessionToUse;
        } else {
          setError('Failed to create session. Please try again.');
          return;
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to create session. Please try again.';
        console.error('[useChat] Failed to create session:', err);
        setError(errorMessage);
        return;
      }
    }

    if (!sessionToUse) {
      setError('No session available. Please wait...');
      return;
    }

    setError(null);
    resetStreamingState();

    const userMessage: Message = {
      id: uuidv4(),
      role: 'user',
      content: content.trim(),
      timestamp: new Date(),
    };

    // Add user message and loading placeholder
    const loadingMessageId = uuidv4();
    const loadingMessage: Message = {
      id: loadingMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isLoading: true,
    };

    setMessages(prev => [...prev, userMessage, loadingMessage]);
    setIsLoading(true);
    setMessageCount(prev => prev + 1);
    setStreamingState(prev => ({ ...prev, isStreaming: true }));

    try {
      // Create new abort controller for this request
      const controller = new AbortController();
      abortControllerRef.current = controller;

      // Use streaming API
      await streamAgent(
        {
          query: content.trim(),
          session_id: sessionToUse,
          user_id: userId,
        },
        {
          onStatus: (message) => {
            setStreamingState(prev => ({ ...prev, currentStatus: message }));
          },
          onTool: (toolName) => {
            streamingToolsRef.current = [...streamingToolsRef.current, toolName];
            setStreamingState(prev => ({
              ...prev,
              toolCalls: streamingToolsRef.current,
            }));
          },
          onComplete: (data: StreamEvent) => {
            // Update streaming state with final data
            setStreamingState(prev => ({
              ...prev,
              isStreaming: false,
              currentStatus: '',
              researcherOutput: data.researcher_output || '',
              validatorOutput: data.validator_output || '',
              validationResult: data.validation_result,
            }));

            // Create final assistant message
            const assistantMessage: Message = {
              id: loadingMessageId,
              role: 'assistant',
              content: data.response || '',
              timestamp: new Date(),
              sources: data.sources?.map(s => ({
                doc_id: s.doc_id,
                content_preview: s.content_preview,
                metadata: {},
              })),
              toolCalls: data.tool_calls,
              researcherOutput: data.researcher_output,
              validatorOutput: data.validator_output,
              validationResult: data.validation_result,
            };

            setMessages(prev =>
              prev.map(m => (m.id === loadingMessageId ? assistantMessage : m))
            );

            setIsLoading(false);
            abortControllerRef.current = null;

            // Auto-update session name from first message if session has no name
            if (messageCount === 0 && sessionToUse) {
              const sessionName = content.trim().slice(0, 50);
              updateSession(sessionToUse, { name: sessionName }).catch(err => {
                console.warn('Failed to update session name:', err);
              });
            }
          },
          onError: (errorMessage) => {
            setStreamingState(prev => ({ ...prev, isStreaming: false }));
            setError(errorMessage);

            // Update loading message to show error
            setMessages(prev =>
              prev.map(m =>
                m.id === loadingMessageId
                  ? {
                    ...m,
                    content: errorMessage === 'Stopped by user' ? 'Stopped by user.' : 'Sorry, I encountered an error. Please try again.',
                    isLoading: false,
                  }
                  : m
              )
            );
            setIsLoading(false);
            abortControllerRef.current = null;
          },
        },
        controller.signal
      );
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to get response';
      setError(errorMessage);
      setStreamingState(prev => ({ ...prev, isStreaming: false }));

      // Update loading message to show error
      setMessages(prev =>
        prev.map(m =>
          m.id === loadingMessageId
            ? {
              ...m,
              content: 'Sorry, I encountered an error processing your request. Please try again.',
              isLoading: false,
            }
            : m
        )
      );
      setIsLoading(false);
    }
  }, [isLoading, effectiveSessionId, userId, messageCount, updateSession, createNewSession, resetStreamingState]);

  const clearChat = useCallback(() => {
    setMessages([]);
    setMessageCount(0);
    resetStreamingState();
  }, [resetStreamingState]);

  const getLastResponse = useCallback((): Message | null => {
    const assistantMessages = messages.filter(m => m.role === 'assistant' && !m.isLoading);
    return assistantMessages[assistantMessages.length - 1] || null;
  }, [messages]);

  return {
    messages,
    isLoading: isLoading || isLoadingMessages,
    error,
    sessionId: effectiveSessionId,
    messageCount,
    streamingState,
    sendMessage,
    clearChat,
    stopGeneration,
    getLastResponse,
  };
}
