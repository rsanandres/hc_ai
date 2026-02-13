'use client';

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';

interface DebugModeContextType {
    debugMode: boolean;
    toggleDebugMode: () => void;
    setDebugMode: (enabled: boolean) => void;
}

const DebugModeContext = createContext<DebugModeContextType | undefined>(undefined);

const STORAGE_KEY = 'atlas-debug-mode';

export function DebugModeProvider({ children }: { children: ReactNode }) {
    const [debugMode, setDebugModeState] = useState(true);

    // Load preference from localStorage on mount (only override if explicitly disabled)
    useEffect(() => {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored === 'false' && debugMode) {
            // eslint-disable-next-line react-hooks/set-state-in-effect
            setDebugModeState(false);
        }
    }, [debugMode]);

    const setDebugMode = useCallback((enabled: boolean) => {
        setDebugModeState(enabled);
        localStorage.setItem(STORAGE_KEY, String(enabled));
    }, []);

    const toggleDebugMode = useCallback(() => {
        setDebugMode(!debugMode);
    }, [debugMode, setDebugMode]);

    return (
        <DebugModeContext.Provider value={{ debugMode, toggleDebugMode, setDebugMode }}>
            {children}
        </DebugModeContext.Provider>
    );
}

export function useDebugMode() {
    const context = useContext(DebugModeContext);
    if (context === undefined) {
        throw new Error('useDebugMode must be used within a DebugModeProvider');
    }
    return context;
}
