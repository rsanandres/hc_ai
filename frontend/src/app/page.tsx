'use client';

import { useEffect, useRef, useState } from 'react';
import { MainLayout } from '@/components/layout/MainLayout';
import { ChatPanel } from '@/components/chat/ChatPanel';
import { WorkflowPanel } from '@/components/workflow/WorkflowPanel';
import { ObservabilityPanel } from '@/components/observability/ObservabilityPanel';
import { ConnectModal } from '@/components/lead-capture/ConnectModal';
import { WelcomeScreen } from '@/components/WelcomeScreen';
import { OnboardingTour } from '@/components/OnboardingTour';
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
  const [referencePanelCollapsed, setReferencePanelCollapsed] = useState(false);
  const [showTour, setShowTour] = useState(false);

  // Track which pipeline steps have been activated to avoid duplicates
  const activatedStepsRef = useRef(new Set<string>());

  // Search tools that trigger vector_search/rerank pipeline steps
  const SEARCH_TOOLS = ['search_clinical_notes', 'get_patient_timeline'];

  // Start workflow when sending a message
  // patientIdOverride bypasses React state race condition (e.g. from WelcomeScreen)
  const handleSend = (message: string, patientIdOverride?: string) => {
    setLastQuery(message);
    setChatInput('');
    activatedStepsRef.current = new Set();
    resetPipeline();
    activateStep('query');
    sendMessage(message, patientIdOverride);
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

    // Status-based transitions (match backend SSE status messages)
    if (status.includes('Starting')) activate('pii_mask');
    if (status.includes('Researcher') || status.includes('investigating')) {
      activate('llm_react');
    }
    if (status.includes('Using ')) {
      // Tool usage — activate llm_react if not already
      activate('llm_react');
    }
    if (status.includes('Synthesizing')) {
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

  // Welcome screen handler
  const handleWelcomeStart = (patient: { id: string; name: string }, prompt: string) => {
    setSelectedPatient(patient);
    setReferencePanelCollapsed(true); // Switch right panel to Pipeline tab
    // Pass patient.id directly to avoid race condition where React state
    // hasn't re-rendered before sendMessage captures the old patientId
    setTimeout(() => handleSend(prompt, patient.id), 50);
  };

  // Handle prompt selection from reference panel — send immediately and collapse
  const handlePromptSelect = (prompt: string) => {
    setReferencePanelCollapsed(true);
    handleSend(prompt);
  };

  // Disable maintenance banner for local testing
  const disableMaintenance = process.env.NEXT_PUBLIC_DISABLE_MAINTENANCE === 'true';

  // Show welcome screen when no patient selected and no messages
  const showWelcome = !selectedPatient && messages.length === 0;

  if (showWelcome) {
    return <WelcomeScreen onStart={handleWelcomeStart} />;
  }

  return (
    <>
      {isMaintenanceMode && !disableMaintenance && (
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
            pointerEvents: 'none',
            '& .MuiAlert-message': { textAlign: 'center', width: '100%' },
          }}
        >
          System is updating — queries may be temporarily unavailable. This page will auto-recover.
        </Alert>
      )}
      <MainLayout
        closeRightPanel={referencePanelCollapsed}
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
            onShowTour={() => setShowTour(true)}
          />
        }
        workflowPanel={
          <WorkflowPanel
            pipeline={pipeline}
            toolCalls={lastToolCalls}
            lastResponse={getLastResponse()}
            isProcessing={isProcessing}
            lastQuery={displayQuery}
            onPromptSelect={handlePromptSelect}
            selectedPatient={selectedPatient}
            onPatientSelect={setSelectedPatient}
            referencePanelCollapsed={referencePanelCollapsed}
          />
        }
        observabilityPanel={
          <ObservabilityPanel
            serviceHealth={serviceHealth}
            metricSummaries={metricSummaries}
            rerankerStats={rerankerStats}
            databaseStats={databaseStats}
            cloudWatchTimeSeries={cloudWatchTimeSeries}
            lastUpdated={lastUpdated}
            onRefresh={refreshData}
            isLoading={obsLoading}
          />
        }
      />



      <OnboardingTour forceShow={showTour} onDismiss={() => setShowTour(false)} />

      <ConnectModal
        open={leadOpen}
        onClose={dismissLead}
      />
    </>
  );
}

