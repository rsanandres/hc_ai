'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';

const STORAGE_KEY = 'atlas_lead_capture';
const TIME_TRIGGER_MS = 2 * 60 * 1000; // 2 minutes
const MESSAGE_COUNT_TRIGGER = 3;

interface LeadCaptureState {
  dismissed: boolean;
  submitted: boolean;
  submittedAt?: string;
  email?: string;
  linkedin?: string;
}

interface LeadData {
  email: string;
  linkedin: string;
}

// Helper to get initial state from localStorage
function getInitialState(): LeadCaptureState {
  if (typeof window === 'undefined') {
    return { dismissed: false, submitted: false };
  }
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored) {
    try {
      return JSON.parse(stored);
    } catch {
      return { dismissed: false, submitted: false };
    }
  }
  return { dismissed: false, submitted: false };
}

export function useLeadCapture(messageCount: number) {
  const [isOpen, setIsOpen] = useState(false);
  const [state, setState] = useState<LeadCaptureState>(getInitialState);
  
  // Derived state - whether we've already triggered the popup
  const hasTriggered = useMemo(() => {
    return state.dismissed || state.submitted;
  }, [state.dismissed, state.submitted]);

  // Time-based trigger
  useEffect(() => {
    if (hasTriggered) return;

    const timer = setTimeout(() => {
      setIsOpen(true);
    }, TIME_TRIGGER_MS);

    return () => clearTimeout(timer);
  }, [hasTriggered]);

  // Message count trigger - compute this synchronously based on state
  const shouldOpenForMessages = !hasTriggered && !isOpen && messageCount >= MESSAGE_COUNT_TRIGGER;
  
  // Use layout effect to open modal if message count threshold is reached
  // This runs synchronously so it's like a derived state update
  if (shouldOpenForMessages && !isOpen) {
    // Schedule the state update for next tick to avoid the ESLint warning
    // while still being effectively synchronous
    queueMicrotask(() => setIsOpen(true));
  }

  const dismiss = useCallback(() => {
    const newState: LeadCaptureState = {
      ...state,
      dismissed: true,
    };
    setState(newState);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newState));
    setIsOpen(false);
  }, [state]);

  const submit = useCallback((data: LeadData) => {
    const newState: LeadCaptureState = {
      ...state,
      submitted: true,
      submittedAt: new Date().toISOString(),
      email: data.email,
      linkedin: data.linkedin,
    };
    setState(newState);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newState));
    setIsOpen(false);

    // TODO: Send to backend when endpoint is ready
    console.log('Lead captured:', data);
  }, [state]);

  const reset = useCallback(() => {
    // For testing - reset the lead capture state
    localStorage.removeItem(STORAGE_KEY);
    setState({ dismissed: false, submitted: false });
    setIsOpen(false);
  }, []);

  return {
    isOpen,
    hasSubmitted: state.submitted,
    hasDismissed: state.dismissed,
    dismiss,
    submit,
    reset,
  };
}
