'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { Message } from '@/types';
import { streamAgent, StreamEvent } from '@/services/streamAgent';
import { useSessions } from './useSessions';
// import { useUser } from './useUser'; // Not needed if we use userId from useSessions or passed in

// Streaming state for real-time updates (debug mode)
// Agent step for sequential display
export interface AgentStep {
  type: 'researcher' | 'validator' | 'response' | 'tool_result';
  output: string;
  iteration: number;
  result?: string; // For validator (APPROVED/REVISION_NEEDED)
  toolName?: string; // For tool_result
}

// Streaming state for real-time updates (debug mode)
export interface StreamingState {
  isStreaming: boolean;
  currentStatus: string;
  toolCalls: string[];
  steps: AgentStep[];  // Array of all agent steps in order
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
  steps: [],
};

export function useChat(sessionId?: string) {
  // const { userId } = useUser(); // Get userId from useSessions to avoid duplicate hooks if possible, or keep it
  const {
    activeSessionId,
    loadSessionMessages,
    updateSession,
    createNewSession,
    saveGuestMessage,
    userId
  } = useSessions();
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
    // Always clear current messages and reset state when session changes
    console.log('[useChat] Session changed to:', effectiveSessionId);
    setMessages([]);
    setMessageCount(0);
    resetStreamingState();

    // Then load messages for the new session
    if (effectiveSessionId) {
      loadMessagesForSession(effectiveSessionId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveSessionId]); // Only depend on session ID, not the callback

  // Reset streaming state helper
  const resetStreamingState = useCallback(() => {
    console.log('[useChat] resetStreamingState called - clearing steps');
    streamingToolsRef.current = [];
    setStreamingState({ ...initialStreamingState });
  }, []);

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoading) return;

    // Check agent service health before sending message
    try {
      const healthUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/agent/health`;
      const healthController = new AbortController();
      const healthTimeout = setTimeout(() => healthController.abort(), 3000);

      const healthResponse = await fetch(healthUrl, {
        signal: healthController.signal
      });
      clearTimeout(healthTimeout);

      if (!healthResponse.ok) {
        throw new Error('Agent service is not healthy');
      }
    } catch (err) {
      console.error('[useChat] Health check failed:', err);
      setError('Agent service unavailable. Is the backend running?');
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



    // Save user message for guests immediately
    if (sessionToUse) {
      saveGuestMessage(sessionToUse, {
        role: 'user',
        text: content.trim(),
        turn_ts: new Date().toISOString(),
      });
    }

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
            console.log('[useChat] onStatus:', message);
            setStreamingState(prev => ({ ...prev, currentStatus: message }));
          },
          onTool: (toolName) => {
            console.log('[useChat] onTool:', toolName);
            streamingToolsRef.current = [...streamingToolsRef.current, toolName];
            setStreamingState(prev => ({
              ...prev,
              toolCalls: streamingToolsRef.current,
            }));
          },
          onToolResult: (toolName, output) => {
            console.log('[useChat] onToolResult:', { toolName, outputLength: output.length });
            setStreamingState(prev => ({
              ...prev,
              steps: [...prev.steps, { type: 'tool_result', output, iteration: 0, toolName }],
            }));
          },
          onResearcherOutput: (output, iteration) => {
            console.log('[useChat] onResearcherOutput:', { iteration, outputLength: output.length });
            setStreamingState(prev => ({
              ...prev,
              steps: [...prev.steps, { type: 'researcher', output, iteration }],
            }));
          },
          onValidatorOutput: (output, result, iteration) => {
            console.log('[useChat] onValidatorOutput:', { iteration, result, outputLength: output.length });
            setStreamingState(prev => ({
              ...prev,
              steps: [...prev.steps, { type: 'validator', output, iteration, result }],
            }));
          },
          onResponseOutput: (output, iteration) => {
            console.log('[useChat] onResponseOutput:', { iteration, outputLength: output.length });
            setStreamingState(prev => ({
              ...prev,
              steps: [...prev.steps, { type: 'response', output, iteration }],
            }));
          },
          onComplete: (data: StreamEvent) => {
            // Update streaming state - steps already accumulated
            setStreamingState(prev => ({
              ...prev,
              isStreaming: false,
              currentStatus: '',
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

            // Save assistant message for guests
            if (sessionToUse) {
              saveGuestMessage(sessionToUse, {
                role: 'assistant',
                text: assistantMessage.content,
                turn_ts: new Date().toISOString(),
                meta: {
                  tool_calls: data.tool_calls,
                  sources: data.sources,
                  researcher_output: data.researcher_output,
                  validator_output: data.validator_output,
                  validation_result: data.validation_result,
                }
              });
            }

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
