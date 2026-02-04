/**
 * Email Verification Page Component
 */
'use client';

import { useState, useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import axios from '@/utils/axiosInstance';
import Link from 'next/link';

export function VerifyEmail() {
    const searchParams = useSearchParams();
    const router = useRouter();
    const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
    const [message, setMessage] = useState('');

    useEffect(() => {
        const token = searchParams.get('token');

        if (!token) {
            setStatus('error');
            setMessage('No verification token provided');
            return;
        }

        const verifyEmail = async () => {
            try {
                const { data } = await axios.get(`/auth/verify?token=${token}`);
                setStatus('success');
                setMessage(data.message || 'Email verified successfully!');

                // Redirect to login after 3 seconds
                setTimeout(() => {
                    router.push('/login');
                }, 3000);
            } catch (error: any) {
                setStatus('error');
                setMessage(error.response?.data?.detail || 'Verification failed. The link may have expired.');
            }
        };

        verifyEmail();
    }, [searchParams, router]);

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-green-50 to-teal-100 px-4">
            <div className="max-w-md w-full space-y-8 bg-white p-8 rounded-xl shadow-lg text-center">
                {status === 'loading' && (
                    <>
                        <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-blue-600 mx-auto"></div>
                        <h2 className="text-2xl font-bold text-gray-900">Verifying your email...</h2>
                        <p className="text-gray-600">Please wait while we verify your account</p>
                    </>
                )}

                {status === 'success' && (
                    <>
                        <div className="bg-green-100 rounded-full h-16 w-16 flex items-center justify-center mx-auto">
                            <svg className="h-10 w-10 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                        </div>
                        <h2 className="text-2xl font-bold text-gray-900">Email Verified!</h2>
                        <p className="text-gray-600">{message}</p>
                        <p className="text-sm text-gray-500">Redirecting to login...</p>
                        <Link
                            href="/login"
                            className="inline-block px-6 py-3 border border-transparent rounded-lg text-white bg-green-600 hover:bg-green-700 font-medium transition-colors"
                        >
                            Go to Login
                        </Link>
                    </>
                )}

                {status === 'error' && (
                    <>
                        <div className="bg-red-100 rounded-full h-16 w-16 flex items-center justify-center mx-auto">
                            <svg className="h-10 w-10 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </div>
                        <h2 className="text-2xl font-bold text-gray-900">Verification Failed</h2>
                        <p className="text-gray-600">{message}</p>
                        <div className="flex flex-col gap-3">
                            <Link
                                href="/register"
                                className="inline-block px-6 py-3 border border-transparent rounded-lg text-white bg-blue-600 hover:bg-blue-700 font-medium transition-colors"
                            >
                                Try Registering Again
                            </Link>
                            <Link
                                href="/login"
                                className="inline-block px-6 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 font-medium transition-colors"
                            >
                                Back to Login
                            </Link>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
