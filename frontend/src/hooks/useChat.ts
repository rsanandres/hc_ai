'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { Message, AgentQueryResponse } from '@/types';
import { queryAgent } from '@/services/agentApi';

const SESSION_STORAGE_KEY = 'atlas_session_id';
const MESSAGES_STORAGE_KEY = 'atlas_messages';

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string>('');
  const messageCountRef = useRef(0);

  // Initialize session from localStorage
  useEffect(() => {
    const storedSessionId = localStorage.getItem(SESSION_STORAGE_KEY);
    const storedMessages = localStorage.getItem(MESSAGES_STORAGE_KEY);
    
    if (storedSessionId) {
      setSessionId(storedSessionId);
    } else {
      const newSessionId = uuidv4();
      setSessionId(newSessionId);
      localStorage.setItem(SESSION_STORAGE_KEY, newSessionId);
    }

    if (storedMessages) {
      try {
        const parsed = JSON.parse(storedMessages);
        setMessages(parsed.map((m: Message) => ({
          ...m,
          timestamp: new Date(m.timestamp),
        })));
        messageCountRef.current = parsed.filter((m: Message) => m.role === 'user').length;
      } catch {
        // Invalid stored messages, start fresh
      }
    }
  }, []);

  // Persist messages to localStorage
  useEffect(() => {
    if (messages.length > 0) {
      localStorage.setItem(MESSAGES_STORAGE_KEY, JSON.stringify(messages));
    }
  }, [messages]);

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoading) return;

    setError(null);
    
    const userMessage: Message = {
      id: uuidv4(),
      role: 'user',
      content: content.trim(),
      timestamp: new Date(),
    };

    // Add user message and loading placeholder
    const loadingMessage: Message = {
      id: uuidv4(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isLoading: true,
    };

    setMessages(prev => [...prev, userMessage, loadingMessage]);
    setIsLoading(true);
    messageCountRef.current += 1;

    try {
      const response: AgentQueryResponse = await queryAgent({
        query: content.trim(),
        session_id: sessionId,
      });

      const assistantMessage: Message = {
        id: loadingMessage.id,
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
        sources: response.sources,
        toolCalls: response.tool_calls,
      };

      setMessages(prev => 
        prev.map(m => m.id === loadingMessage.id ? assistantMessage : m)
      );
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to get response';
      setError(errorMessage);
      
      // Update loading message to show error
      setMessages(prev => 
        prev.map(m => m.id === loadingMessage.id ? {
          ...m,
          content: 'Sorry, I encountered an error processing your request. Please try again.',
          isLoading: false,
        } : m)
      );
    } finally {
      setIsLoading(false);
    }
  }, [isLoading, sessionId]);

  const clearChat = useCallback(() => {
    setMessages([]);
    messageCountRef.current = 0;
    localStorage.removeItem(MESSAGES_STORAGE_KEY);
    // Generate new session
    const newSessionId = uuidv4();
    setSessionId(newSessionId);
    localStorage.setItem(SESSION_STORAGE_KEY, newSessionId);
  }, []);

  const getLastResponse = useCallback((): Message | null => {
    const assistantMessages = messages.filter(m => m.role === 'assistant' && !m.isLoading);
    return assistantMessages[assistantMessages.length - 1] || null;
  }, [messages]);

  return {
    messages,
    isLoading,
    error,
    sessionId,
    messageCount: messageCountRef.current,
    sendMessage,
    clearChat,
    getLastResponse,
  };
}
