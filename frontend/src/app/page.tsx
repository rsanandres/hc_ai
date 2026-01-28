'use client';

import { useEffect, useState } from 'react';
import { MainLayout } from '@/components/layout/MainLayout';
import { ChatPanel } from '@/components/chat/ChatPanel';
import { WorkflowPanel } from '@/components/workflow/WorkflowPanel';
import { ObservabilityPanel } from '@/components/observability/ObservabilityPanel';
import { ConnectModal } from '@/components/lead-capture/ConnectModal';
import { SessionSidebar } from '@/components/session/SessionSidebar';
import { useChat } from '@/hooks/useChat';
import { useWorkflow } from '@/hooks/useWorkflow';
import { IconButton, Tooltip, alpha, Box } from '@mui/material';
import { Menu, User } from 'lucide-react';
import { useObservability } from '@/hooks/useObservability';
import { useLeadCapture } from '@/hooks/useLeadCapture';
import { useSessions } from '@/hooks/useSessions';
import { getMockCostBreakdown } from '@/services/mockData';
import { LoginModal } from '@/components/auth/LoginModal';

export default function Home() {
  const { switchSession, login, userId } = useSessions();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loginModalOpen, setLoginModalOpen] = useState(false);
  const { messages, isLoading, error, sendMessage, stopGeneration, clearChat, getLastResponse, messageCount, streamingState } = useChat();
  const { pipeline, lastToolCalls, isProcessing, startProcessing, updateFromResponse } = useWorkflow();
  const {
    serviceHealth,
    metricSummaries,
    cloudWatchMetrics,
    langSmithTraces,
    lastUpdated,
    refreshData,
    isLoading: obsLoading,
  } = useObservability();
  const { isOpen: leadOpen, dismiss: dismissLead } = useLeadCapture(messageCount);

  // Track the last query for workflow display
  const [lastQuery, setLastQuery] = useState<string>('');

  // Start workflow animation when sending a message
  const handleSend = (message: string) => {
    setLastQuery(message);
    startProcessing();
    sendMessage(message);
  };

  // Update workflow when response arrives
  useEffect(() => {
    if (!isLoading) {
      const lastResponse = getLastResponse();
      updateFromResponse(lastResponse);
    }
  }, [isLoading, getLastResponse, updateFromResponse]);

  // Get the last user message for workflow display (fallback to tracked query)
  const lastUserMessage = messages.filter(m => m.role === 'user').pop();
  const displayQuery = lastUserMessage?.content || lastQuery;

  const handleSessionSelect = (sessionId: string) => {
    switchSession(sessionId);
    setSidebarOpen(false);
  };

  return (
    <>
      <SessionSidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onSessionSelect={handleSessionSelect}
      />
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
          />
        }
        workflowPanel={
          <WorkflowPanel
            pipeline={pipeline}
            toolCalls={lastToolCalls}
            lastResponse={getLastResponse()}
            isProcessing={isProcessing}
            lastQuery={displayQuery}
          />
        }
        observabilityPanel={
          <ObservabilityPanel
            serviceHealth={serviceHealth}
            metricSummaries={metricSummaries}
            cloudWatchMetrics={cloudWatchMetrics}
            langSmithTraces={langSmithTraces}
            costBreakdown={getMockCostBreakdown()}
            lastUpdated={lastUpdated}
            onRefresh={refreshData}
            isLoading={obsLoading}
          />
        }
        leftActionBar={
          <>
            <Tooltip title="Sessions" arrow placement="right">
              <IconButton
                onClick={() => setSidebarOpen(true)}
                sx={{
                  color: 'text.secondary',
                  width: 40,
                  height: 40,
                  borderRadius: '12px',
                  transition: 'all 0.2s',
                  '&:hover': {
                    color: 'primary.main',
                    bgcolor: (theme) => alpha(theme.palette.primary.main, 0.1),
                    transform: 'scale(1.05)',
                  },
                }}
              >
                <Menu size={20} strokeWidth={2} />
              </IconButton>
            </Tooltip>
          </>
        }
      />

      {/* Top Right User Profile Button */}
      <Box sx={{ position: 'fixed', top: 16, right: 16, zIndex: 1200 }}>
        <Tooltip title={userId ? `Signed in as: ${userId}` : "Switch User / Login"}>
          <IconButton
            onClick={() => setLoginModalOpen(true)}
            sx={{
              bgcolor: (theme) => alpha(theme.palette.background.paper, 0.8),
              backdropFilter: 'blur(8px)',
              border: '1px solid',
              borderColor: 'divider',
              boxShadow: 2,
              width: 44,
              height: 44,
              '&:hover': {
                bgcolor: 'background.paper',
                transform: 'scale(1.05)',
              },
            }}
          >
            <User size={20} />
          </IconButton>
        </Tooltip>
      </Box>

      <LoginModal
        open={loginModalOpen}
        onClose={() => setLoginModalOpen(false)}
        onLogin={login}
        currentUserId={userId || ''}
      />

      <ConnectModal
        open={leadOpen}
        onClose={dismissLead}
      />
    </>
  );
}

