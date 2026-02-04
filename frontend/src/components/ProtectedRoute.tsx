/**
 * ProtectedRoute wrapper - Redirects to login if not authenticated
 */
'use client';

import { useContext, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { AuthContext } from '@/contexts/AuthContext';

interface ProtectedRouteProps {
    children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
    const { isAuthenticated, isLoading } = useContext(AuthContext);
    const router = useRouter();

    useEffect(() => {
        if (!isLoading && !isAuthenticated) {
            console.log('[ProtectedRoute] Not authenticated, redirecting to login');
            router.push('/login');
        }
    }, [isAuthenticated, isLoading, router]);

    // Show loading while checking auth
    if (isLoading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                    <p className="text-gray-600">Loading...</p>
                </div>
            </div>
        );
    }

    // Don't render content if not authenticated
    if (!isAuthenticated) {
        return null;
    }

    return <>{children}</>;
}
