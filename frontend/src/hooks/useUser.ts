'use client';

import { useState, useEffect } from 'react';

/**
 * Simple browser fingerprint implementation
 * Combines user agent, screen dimensions, timezone, and language
 * to generate a consistent user ID without external libraries
 */
function generateBrowserFingerprint(): string {
  const components: string[] = [];

  // User agent
  if (typeof navigator !== 'undefined' && navigator.userAgent) {
    components.push(navigator.userAgent);
  }

  // Screen dimensions
  if (typeof screen !== 'undefined') {
    components.push(`${screen.width}x${screen.height}`);
    components.push(`${screen.availWidth}x${screen.availHeight}`);
    components.push(screen.colorDepth?.toString() || '');
  }

  // Timezone
  try {
    components.push(Intl.DateTimeFormat().resolvedOptions().timeZone);
  } catch {
    // Fallback if timezone not available
  }

  // Language
  if (typeof navigator !== 'undefined') {
    components.push(navigator.language || '');
    if (navigator.languages) {
      components.push(navigator.languages.join(','));
    }
  }

  // Combine all components and create a hash-like string
  const combined = components.join('|');

  // Simple hash function (not cryptographic, just for consistency)
  let hash = 0;
  for (let i = 0; i < combined.length; i++) {
    const char = combined.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32-bit integer
  }

  // Convert to positive hex string
  return Math.abs(hash).toString(16).padStart(8, '0');
}

export function useUser() {
  const [userId, setUserId] = useState<string>('');
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    // Mark as client-side only
    if (!isClient) {
      setIsClient(true);
    }

    // Check localStorage first
    const storedId = localStorage.getItem('atlas_user_device_id');
    if (storedId) {
      setUserId(storedId);
    } else {
      // Generate fingerprint and save it
      const fingerprint = generateBrowserFingerprint();
      localStorage.setItem('atlas_user_device_id', fingerprint);
      setUserId(fingerprint);
    }
  }, [isClient]);

  const login = (newUserId: string) => {
    localStorage.setItem('atlas_user_device_id', newUserId);
    setUserId(newUserId);
    // Force reload to refresh sessions with new ID
    window.location.reload();
  };

  const logout = () => {
    localStorage.removeItem('atlas_user_device_id');
    const fingerprint = generateBrowserFingerprint();
    setUserId(fingerprint);
    // Force reload to refresh sessions
    window.location.reload();
  };

  return { userId, isClient, login, logout };
}
