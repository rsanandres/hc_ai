'use client';

import { useState, useCallback, useRef } from 'react';
import { PipelineStep, Message } from '@/types';

// Timing tracker for pipeline steps
interface StepTiming {
  startTime?: number;
  endTime?: number;
}

// Default pipeline steps that match the RAG workflow
const DEFAULT_PIPELINE: PipelineStep[] = [
  {
    id: 'query',
    name: 'Query Input',
    description: 'User query received',
    status: 'pending',
  },
  {
    id: 'pii_mask',
    name: 'PII Masking',
    description: 'AWS Comprehend Medical PHI detection',
    status: 'pending',
  },
  {
    id: 'vector_search',
    name: 'Vector Search',
    description: 'Hybrid BM25 + semantic search on pgvector',
    status: 'pending',
  },
  {
    id: 'rerank',
    name: 'Filtering',
    description: 'Auto resource-type detection and filtering',
    status: 'pending',
  },
  {
    id: 'llm_react',
    name: 'Researcher',
    description: 'Claude 3.5 Sonnet reasoning with tools',
    status: 'pending',
  },
  {
    id: 'response',
    name: 'Response Synthesis',
    description: 'Claude 3.5 Haiku generates final response',
    status: 'pending',
  },
];

// Map tool calls to pipeline steps
const TOOL_TO_STEP: Record<string, string[]> = {
  search_clinical_notes: ['vector_search', 'rerank'],
  get_patient_timeline: ['vector_search', 'rerank'],
  cross_reference_meds: ['llm_react'],
  get_session_context: ['llm_react'],
  calculate: ['llm_react'],
  get_current_date: ['llm_react'],
};

export function useWorkflow() {
  const [pipeline, setPipeline] = useState<PipelineStep[]>(DEFAULT_PIPELINE);
  const [lastToolCalls, setLastToolCalls] = useState<string[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);

  // Track timing for each step
  const stepTimings = useRef<Record<string, StepTiming>>({});
  const processingStartTime = useRef<number>(0);

  // Reset pipeline to pending state
  const resetPipeline = useCallback(() => {
    setPipeline(DEFAULT_PIPELINE.map(step => ({ ...step, status: 'pending', details: undefined })));
    setLastToolCalls([]);
    stepTimings.current = {};
  }, []);

  // Activate a pipeline step based on real SSE events.
  // Completes the currently active step (with real duration) and activates the new one.
  const activateStep = useCallback((stepId: string) => {
    const now = Date.now();

    // First call starts the processing timer
    if (processingStartTime.current === 0) {
      processingStartTime.current = now;
      setIsProcessing(true);
    }

    // Start timing for the new step
    if (!stepTimings.current[stepId]) {
      stepTimings.current[stepId] = { startTime: now };
    }

    setPipeline(prev => {
      // Find the currently active step to complete it
      const activeStep = prev.find(s => s.status === 'active');

      // End timing for the currently active step
      if (activeStep && activeStep.id !== stepId) {
        const timing = stepTimings.current[activeStep.id];
        if (timing?.startTime && !timing.endTime) {
          timing.endTime = now;
        }
      }

      return prev.map(step => {
        if (step.id === stepId) {
          return { ...step, status: 'active' };
        }
        // Complete the previously active step with real duration
        if (activeStep && step.id === activeStep.id && step.id !== stepId) {
          const timing = stepTimings.current[step.id];
          const duration = timing?.startTime && timing?.endTime
            ? timing.endTime - timing.startTime
            : undefined;
          return { ...step, status: 'completed', duration };
        }
        return step;
      });
    });
  }, []);

  // Update pipeline based on response
  const updateFromResponse = useCallback((response: Message | null) => {
    if (!response) return;

    const endTime = Date.now();
    const totalLatency = processingStartTime.current
      ? endTime - processingStartTime.current
      : 0;

    setIsProcessing(false);
    const toolCalls = response.toolCalls || [];
    const sources = response.sources || [];
    setLastToolCalls(toolCalls);

    // Determine which steps were actually used
    const usedSteps = new Set<string>(['query', 'pii_mask', 'response']);

    // Add steps based on tool calls
    toolCalls.forEach(tool => {
      const steps = TOOL_TO_STEP[tool];
      if (steps) {
        steps.forEach(step => usedSteps.add(step));
      }
    });

    // If any search tool was called, mark vector_search and rerank as completed
    if (toolCalls.some(t => t.includes('search') || t.includes('timeline'))) {
      usedSteps.add('vector_search');
      usedSteps.add('rerank');
    }

    // Always mark llm_react as used (LLM always runs)
    usedSteps.add('llm_react');

    // Calculate details for each step — use real data where available, null for unavailable
    const iterationCount = response.iterationCount;
    const stepDetails: Record<string, Record<string, unknown>> = {
      query: {
        // Query details are passed via queryText prop
      },
      pii_mask: {
        // PII masking details — not available from backend yet
        entitiesFound: null,
        namesMasked: null,
        idsMasked: null,
        datesMasked: null,
        processingTime: null,
      },
      vector_search: {
        docsRetrieved: sources.length, // Real
        searchTime: null, // Not available from backend
      },
      rerank: {
        candidatesIn: null, // Not available from backend
        resultsOut: sources.length, // Real
        topScore: null, // Not available from backend
        rerankTime: null,
      },
      llm_react: {
        inputTokens: null, // Not available from backend
        outputTokens: null,
        reasoningSteps: iterationCount ?? (toolCalls.length > 0 ? toolCalls.length : 1), // Real if available
        toolsInvoked: toolCalls.length, // Real
        latency: null,
      },
      response: {
        responseLength: response.content?.length || 0, // Real
        sourcesCited: sources.length, // Real
        piiRemasked: null,
        totalLatency: totalLatency, // Real
      },
    };

    setPipeline(prev => prev.map(step => {
      const timing = stepTimings.current[step.id];
      const realDuration = timing?.startTime && timing?.endTime
        ? timing.endTime - timing.startTime
        : undefined;

      return {
        ...step,
        status: usedSteps.has(step.id) ? 'completed' : 'skipped',
        details: stepDetails[step.id],
        // Preserve real durations from activateStep; use totalLatency for response
        duration: step.id === 'response' ? totalLatency : realDuration,
      };
    }));
  }, []);

  return {
    pipeline,
    lastToolCalls,
    isProcessing,
    resetPipeline,
    activateStep,
    updateFromResponse,
  };
}
