'use client';

import { useState, useEffect, useCallback } from 'react';

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

export function useLeadCapture(messageCount: number) {
  const [isOpen, setIsOpen] = useState(false);
  const [hasTriggered, setHasTriggered] = useState(false);
  const [state, setState] = useState<LeadCaptureState>({
    dismissed: false,
    submitted: false,
  });

  // Load state from localStorage
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        setState(parsed);
        if (parsed.dismissed || parsed.submitted) {
          setHasTriggered(true); // Don't trigger again
        }
      } catch {
        // Invalid stored state
      }
    }
  }, []);

  // Time-based trigger
  useEffect(() => {
    if (hasTriggered || state.dismissed || state.submitted) return;

    const timer = setTimeout(() => {
      setIsOpen(true);
      setHasTriggered(true);
    }, TIME_TRIGGER_MS);

    return () => clearTimeout(timer);
  }, [hasTriggered, state.dismissed, state.submitted]);

  // Message count trigger
  useEffect(() => {
    if (hasTriggered || state.dismissed || state.submitted) return;

    if (messageCount >= MESSAGE_COUNT_TRIGGER) {
      setIsOpen(true);
      setHasTriggered(true);
    }
  }, [messageCount, hasTriggered, state.dismissed, state.submitted]);

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
    setHasTriggered(false);
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
