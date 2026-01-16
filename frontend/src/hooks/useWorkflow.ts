'use client';

import { useState, useCallback, useEffect } from 'react';
import { PipelineStep, Message } from '@/types';

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
    description: 'Scrubbing sensitive data with AWS Comprehend Medical',
    status: 'pending',
  },
  {
    id: 'vector_search',
    name: 'Vector Search',
    description: 'Searching pgvector for relevant documents',
    status: 'pending',
  },
  {
    id: 'rerank',
    name: 'Reranking',
    description: 'Cross-encoder reranking for precision',
    status: 'pending',
  },
  {
    id: 'llm_react',
    name: 'LLM ReAct',
    description: 'Claude 3.5 Haiku reasoning with tools',
    status: 'pending',
  },
  {
    id: 'response',
    name: 'Response',
    description: 'Final response with PII masking',
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

  // Reset pipeline to pending state
  const resetPipeline = useCallback(() => {
    setPipeline(DEFAULT_PIPELINE.map(step => ({ ...step, status: 'pending' })));
    setLastToolCalls([]);
  }, []);

  // Simulate pipeline progress when processing
  const startProcessing = useCallback(() => {
    setIsProcessing(true);
    resetPipeline();
    
    // Animate through steps
    const steps = ['query', 'pii_mask', 'vector_search', 'rerank', 'llm_react'];
    let currentIndex = 0;

    const interval = setInterval(() => {
      if (currentIndex < steps.length) {
        setPipeline(prev => prev.map(step => {
          if (step.id === steps[currentIndex]) {
            return { ...step, status: 'active' };
          }
          if (steps.indexOf(step.id) < currentIndex) {
            return { ...step, status: 'completed' };
          }
          return step;
        }));
        currentIndex++;
      } else {
        clearInterval(interval);
      }
    }, 400);

    return () => clearInterval(interval);
  }, [resetPipeline]);

  // Update pipeline based on response
  const updateFromResponse = useCallback((response: Message | null) => {
    if (!response) return;

    setIsProcessing(false);
    const toolCalls = response.toolCalls || [];
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

    setPipeline(prev => prev.map(step => ({
      ...step,
      status: usedSteps.has(step.id) ? 'completed' : 'skipped',
    })));
  }, []);

  return {
    pipeline,
    lastToolCalls,
    isProcessing,
    resetPipeline,
    startProcessing,
    updateFromResponse,
  };
}
