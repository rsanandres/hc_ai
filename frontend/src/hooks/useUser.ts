'use client';

import { useState, useEffect } from 'react';

/**
 * Simplified user hook for MVP - generates ephemeral user ID
 * No authentication, no persistence
 */
export function useUser() {
  const [userId, setUserId] = useState<string>('');
  const [isClient, setIsClient] = useState(false);

  /* eslint-disable react-hooks/set-state-in-effect -- Hydration pattern: must set client-only state after mount */
  useEffect(() => {
    setIsClient(true);
    // Generate random user ID for this session
    const randomId = `guest_${Math.random().toString(36).slice(2, 10)}`;
    setUserId(randomId);
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  return {
    userId,
    isLoggedIn: false,
    isClient,
    login: () => { },
  };
}
