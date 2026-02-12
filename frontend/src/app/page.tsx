'use client';

import { useEffect, useRef, useState } from 'react';
import { MainLayout } from '@/components/layout/MainLayout';
import { ChatPanel } from '@/components/chat/ChatPanel';
import { WorkflowPanel } from '@/components/workflow/WorkflowPanel';
import { ObservabilityPanel } from '@/components/observability/ObservabilityPanel';
import { ConnectModal } from '@/components/lead-capture/ConnectModal';
import { useChat } from '@/hooks/useChat';
import { useWorkflow } from '@/hooks/useWorkflow';
import { Alert } from '@mui/material';
import { useObservability } from '@/hooks/useObservability';
import { useLeadCapture } from '@/hooks/useLeadCapture';
import { useSessions } from '@/hooks/useSessions';

// Patient type for selection
interface SelectedPatient {
  id: string;
  name: string;
}

export default function Home() {
  const { activeSessionId } = useSessions();

  // Patient selection state - persists across messages
  const [selectedPatient, setSelectedPatient] = useState<SelectedPatient | null>(null);

  const { messages, isLoading, error, sendMessage, stopGeneration, clearChat, getLastResponse, messageCount, streamingState, setFeedback, regenerateMessage } = useChat(activeSessionId, selectedPatient?.id);
  const { pipeline, lastToolCalls, isProcessing, activateStep, updateFromResponse, resetPipeline } = useWorkflow();
  const {
    serviceHealth,
    metricSummaries,
    langSmithTraces,
    rerankerStats,
    databaseStats,
    cloudWatchTimeSeries,
    lastUpdated,
    refreshData,
    isLoading: obsLoading,
  isMaintenanceMode,
  } = useObservability();
  const { isOpen: leadOpen, dismiss: dismissLead } = useLeadCapture(messageCount);

  // Track the last query for workflow display
  const [lastQuery, setLastQuery] = useState<string>('');
  const [chatInput, setChatInput] = useState<string>(''); // Added external input state

  // Track which pipeline steps have been activated to avoid duplicates
  const activatedStepsRef = useRef(new Set<string>());

  // Search tools that trigger vector_search/rerank pipeline steps
  const SEARCH_TOOLS = ['search_clinical_notes', 'get_patient_timeline'];

  // Start workflow when sending a message
  const handleSend = (message: string) => {
    setLastQuery(message);
    setChatInput('');
    activatedStepsRef.current = new Set();
    resetPipeline();
    activateStep('query');
    sendMessage(message);
  };

  // Drive pipeline steps from real SSE streaming events
  useEffect(() => {
    if (!streamingState.isStreaming) return;

    const activate = (stepId: string) => {
      if (!activatedStepsRef.current.has(stepId)) {
        activatedStepsRef.current.add(stepId);
        activateStep(stepId);
      }
    };

    const status = streamingState.currentStatus;

    // Status-based transitions
    if (status.includes('Starting')) activate('pii_mask');
    if (status.includes('Synthesizing')) {
      activate('llm_react'); // Ensure llm_react is activated before response
      activate('response');
    }

    // Tool and step-based transitions
    for (const step of streamingState.steps) {
      if (step.type === 'tool_call' && step.toolName && SEARCH_TOOLS.includes(step.toolName)) {
        activate('vector_search');
      }
      if (step.type === 'tool_result' && step.toolName && SEARCH_TOOLS.includes(step.toolName)) {
        activate('rerank');
      }
      if (step.type === 'researcher') {
        activate('llm_react');
      }
    }
  }, [streamingState, activateStep]);

  // Finalize pipeline when response arrives
  useEffect(() => {
    if (!isLoading) {
      const lastResponse = getLastResponse();
      updateFromResponse(lastResponse);
    }
  }, [isLoading, getLastResponse, updateFromResponse]);

  // Get the last user message for workflow display (fallback to tracked query)
  const lastUserMessage = messages.filter(m => m.role === 'user').pop();
  const displayQuery = lastUserMessage?.content || lastQuery;



  return (
    <>
      {isMaintenanceMode && (
        <Alert
          severity="info"
          sx={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            zIndex: 9999,
            borderRadius: 0,
            justifyContent: 'center',
            py: 0.5,
            '& .MuiAlert-message': { textAlign: 'center', width: '100%' },
          }}
        >
          System is updating — queries may be temporarily unavailable. This page will auto-recover.
        </Alert>
      )}
      <MainLayout
        chatPanel={
          <ChatPanel
            messages={messages}
            isLoading={isLoading}
            error={error}
            onSend={handleSend}
            onStop={stopGeneration}
            onClear={clearChat}
            streamingState={streamingState}
            externalInput={chatInput}
            selectedPatient={selectedPatient}
            onFeedback={setFeedback}
            onRegenerate={regenerateMessage}
          />
        }
        workflowPanel={
          <WorkflowPanel
            pipeline={pipeline}
            toolCalls={lastToolCalls}
            lastResponse={getLastResponse()}
            isProcessing={isProcessing}
            lastQuery={displayQuery}
            onPromptSelect={setChatInput}
            selectedPatient={selectedPatient}
            onPatientSelect={setSelectedPatient}
          />
        }
        observabilityPanel={
          <ObservabilityPanel
            serviceHealth={serviceHealth}
            metricSummaries={metricSummaries}
            langSmithTraces={langSmithTraces}
            rerankerStats={rerankerStats}
            databaseStats={databaseStats}
            cloudWatchTimeSeries={cloudWatchTimeSeries}
            lastUpdated={lastUpdated}
            onRefresh={refreshData}
            isLoading={obsLoading}
          />
        }
      />



      <ConnectModal
        open={leadOpen}
        onClose={dismissLead}
      />
    </>
  );
}

