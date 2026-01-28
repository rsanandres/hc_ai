'use client';

import { AgentQueryRequest } from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Stream event types from backend
export interface StreamEvent {
    type: 'start' | 'status' | 'tool' | 'complete' | 'error';
    message?: string;
    tool?: string;
    // Complete event data
    response?: string;
    researcher_output?: string;
    validator_output?: string;
    validation_result?: string;
    tool_calls?: string[];
    sources?: Array<{ doc_id: string; content_preview: string }>;
    iteration_count?: number;
}

export interface StreamCallbacks {
    onStatus?: (message: string) => void;
    onTool?: (toolName: string) => void;
    onResearcherOutput?: (output: string) => void;
    onValidatorOutput?: (output: string, result?: string) => void;
    onComplete?: (data: StreamEvent) => void;
    onError?: (error: string) => void;
}

/**
 * Stream agent query using Server-Sent Events.
 * Provides real-time updates as the agent processes the query.
 */
export async function streamAgent(
    request: AgentQueryRequest,
    callbacks: StreamCallbacks,
    signal?: AbortSignal
): Promise<void> {
    const internalController = new AbortController();
    const timeout = setTimeout(() => internalController.abort(), 300000); // 5 min timeout

    // Handle external abort
    if (signal) {
        signal.addEventListener('abort', () => {
            internalController.abort();
            clearTimeout(timeout);
        });
    }

    try {
        const response = await fetch(`${API_BASE_URL}/agent/query/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(request),
            signal: internalController.signal,
        });

        if (!response.ok) {
            const errorText = await response.text().catch(() => response.statusText);
            throw new Error(`Stream request failed: ${response.status} ${errorText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
            throw new Error('No response body reader available');
        }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();

            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Process complete SSE messages
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Keep incomplete line in buffer

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;

                try {
                    const data: StreamEvent = JSON.parse(line.slice(6));

                    switch (data.type) {
                        case 'start':
                        case 'status':
                            callbacks.onStatus?.(data.message || '');
                            break;
                        case 'tool':
                            callbacks.onTool?.(data.tool || '');
                            break;
                        case 'complete':
                            callbacks.onComplete?.(data);
                            break;
                        case 'error':
                            callbacks.onError?.(data.message || 'Unknown error');
                            break;
                    }
                } catch {
                    console.warn('[streamAgent] Failed to parse SSE data:', line);
                }
            }
        }
    } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') {
            // If aborted by user (signal) vs timeout
            if (signal?.aborted) {
                callbacks.onStatus?.('Stopped by user');
                return; // Clean exit on user stop
            }
            callbacks.onError?.('Request timed out after 5 minutes');
        } else {
            callbacks.onError?.(error instanceof Error ? error.message : String(error));
        }
    } finally {
        clearTimeout(timeout);
    }
}
