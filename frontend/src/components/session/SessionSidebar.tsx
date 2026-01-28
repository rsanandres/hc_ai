'use client';

import { useState, useEffect } from 'react';
import {
  Box,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  IconButton,
  Typography,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  alpha,
} from '@mui/material';
import { Trash2, MessageSquare, Plus, MoreVertical, X, AlertCircle, Edit } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { useSessions } from '@/hooks/useSessions';
import { SessionMetadata } from '@/types';

interface SessionSidebarProps {
  open: boolean;
  onClose: () => void;
  onSessionSelect: (sessionId: string) => void;
}

export function SessionSidebar({ open, onClose, onSessionSelect }: SessionSidebarProps) {
  const {
    sessions,
    activeSessionId,
    isLoading,
    createNewSession,
    switchSession,
    removeSession,
    updateSession,
    checkSessionLimit,
    maxSessions,
  } = useSessions();

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState<SessionMetadata | null>(null);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [sessionToEdit, setSessionToEdit] = useState<SessionMetadata | null>(null);
  const [editName, setEditName] = useState('');
  const [limitDialogOpen, setLimitDialogOpen] = useState(false);
  const [deleteOldestDialogOpen, setDeleteOldestDialogOpen] = useState(false);
  const [oldestSession, setOldestSession] = useState<SessionMetadata | null>(null);

  const handleNewSession = async () => {
    try {
      const atLimit = await checkSessionLimit();
      if (atLimit) {
        // Find oldest session to propose for deletion
        if (sessions.length > 0) {
          // Assuming sessions are sorted by last_activity desc (newest first)
          // The last one is the oldest
          const oldest = sessions[sessions.length - 1];
          setOldestSession(oldest);
          setDeleteOldestDialogOpen(true);
        } else {
          setLimitDialogOpen(true);
        }
        return;
      }

      const newSession = await createNewSession();
      if (newSession) {
        switchSession(newSession.session_id);
        onSessionSelect(newSession.session_id);
      }
    } catch (err) {
      if (err instanceof Error && err.message === 'SESSION_LIMIT_EXCEEDED') {
        // Fallback if checkSessionLimit didn't catch it but backend did
        if (sessions.length > 0) {
          const oldest = sessions[sessions.length - 1];
          setOldestSession(oldest);
          setDeleteOldestDialogOpen(true);
        } else {
          setLimitDialogOpen(true);
        }
      }
    }
  };

  const handleSessionClick = (sessionId: string) => {
    switchSession(sessionId);
    onSessionSelect(sessionId);
  };

  const handleDeleteClick = (session: SessionMetadata, e: React.MouseEvent) => {
    e.stopPropagation();
    setSessionToDelete(session);
    setDeleteDialogOpen(true);
  };

  const handleEditClick = (session: SessionMetadata, e: React.MouseEvent) => {
    e.stopPropagation();
    setSessionToEdit(session);
    setEditName(session.name || '');
    setEditDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (sessionToDelete) {
      await removeSession(sessionToDelete.session_id);
      setDeleteDialogOpen(false);
      setSessionToDelete(null);
    }
  };

  const confirmDeleteOldest = async () => {
    if (oldestSession) {
      // 1. Delete the oldest session
      await removeSession(oldestSession.session_id);
      setDeleteOldestDialogOpen(false);
      setOldestSession(null);

      // 2. Create the new session
      const newSession = await createNewSession();
      if (newSession) {
        switchSession(newSession.session_id);
        onSessionSelect(newSession.session_id);
      }
    }
  };

  const confirmEdit = async () => {
    if (sessionToEdit) {
      await updateSession(sessionToEdit.session_id, { name: editName });
      setEditDialogOpen(false);
      setSessionToEdit(null);
      setEditName('');
    }
  };

  // Hydration-safe date formatter
  const useFormattedDate = (dateString: string) => {
    const [formatted, setFormatted] = useState(dateString);

    useEffect(() => {
      try {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) {
          setFormatted('Just now');
          return;
        }
        if (diffMins < 60) {
          setFormatted(`${diffMins}m ago`);
          return;
        }
        if (diffHours < 24) {
          setFormatted(`${diffHours}h ago`);
          return;
        }
        if (diffDays < 7) {
          setFormatted(`${diffDays}d ago`);
          return;
        }
        setFormatted(date.toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
          year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
        }));
      } catch {
        setFormatted(dateString);
      }
    }, [dateString]);

    return formatted;
  };

  // Component to render date to avoid hydration mismatch in list
  const SessionDate = ({ date }: { date: string }) => {
    const formatted = useFormattedDate(date);
    return <>{formatted}</>;
  };

  return (
    <>
      <Drawer
        anchor="left"
        open={open}
        onClose={onClose}
        sx={{
          '& .MuiDrawer-paper': {
            width: 280,
            bgcolor: 'background.paper',
            borderRight: 1,
            borderColor: 'divider',
          },
        }}
      >
        <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              Sessions
            </Typography>
            <IconButton size="small" onClick={onClose}>
              <X size={18} />
            </IconButton>
          </Box>
          <Button
            fullWidth
            variant="contained"
            startIcon={<Plus size={18} />}
            onClick={handleNewSession}
            disabled={isLoading || sessions.length >= maxSessions}
            sx={{ mb: 1 }}
          >
            New Session
          </Button>
          {sessions.length >= maxSessions && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center' }}>
              Maximum {maxSessions} sessions
            </Typography>
          )}
        </Box>

        <List sx={{ flex: 1, overflow: 'auto', p: 0 }}>
          {isLoading && sessions.length === 0 ? (
            <ListItem>
              <ListItemText primary="Loading sessions..." />
            </ListItem>
          ) : sessions.length === 0 ? (
            <ListItem>
              <ListItemText
                primary="No sessions"
                secondary="Create a new session to get started"
              />
            </ListItem>
          ) : (
            sessions.map((session) => {
              const isActive = session.session_id === activeSessionId;
              return (
                <ListItem
                  key={session.session_id}
                  disablePadding
                  sx={{
                    '&:hover .session-actions': { opacity: 1 },
                  }}
                >
                  <ListItemButton
                    selected={isActive}
                    onClick={() => handleSessionClick(session.session_id)}
                    sx={{
                      flexDirection: 'column',
                      alignItems: 'flex-start',
                      py: 1.5,
                      px: 2,
                      bgcolor: isActive ? (theme) => alpha(theme.palette.primary.main, 0.1) : 'transparent',
                      '&:hover': {
                        bgcolor: (theme) => alpha(theme.palette.primary.main, 0.05),
                      },
                    }}
                  >
                    <Box sx={{ width: '100%', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Typography
                          variant="subtitle2"
                          sx={{
                            fontWeight: isActive ? 600 : 500,
                            mb: 0.5,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {session.name || 'New Chat'}
                        </Typography>
                        {session.first_message_preview && (
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={{
                              display: 'block',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                              mb: 0.5,
                            }}
                          >
                            {session.first_message_preview}
                          </Typography>
                        )}
                        <Typography variant="caption" color="text.secondary">
                          <SessionDate date={session.last_activity} /> • {session.message_count} messages
                        </Typography>
                      </Box>
                      <Box
                        className="session-actions"
                        sx={{
                          opacity: 0,
                          transition: 'opacity 0.2s',
                          display: 'flex',
                          gap: 0.5,
                          ml: 1,
                        }}
                      >
                        <IconButton
                          size="small"
                          onClick={(e) => handleEditClick(session, e)}
                          sx={{ p: 0.5 }}
                        >
                          <Edit size={16} />
                        </IconButton>
                        <IconButton
                          size="small"
                          onClick={(e) => handleDeleteClick(session, e)}
                          sx={{ p: 0.5 }}
                        >
                          <Trash2 size={16} />
                        </IconButton>
                      </Box>
                    </Box>
                  </ListItemButton>
                </ListItem>
              );
            })
          )}
        </List>
      </Drawer>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle>Delete Session?</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete &quot;{sessionToDelete?.name || 'this session'}&quot;? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button onClick={confirmDelete} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit Session Dialog */}
      <Dialog open={editDialogOpen} onClose={() => setEditDialogOpen(false)}>
        <DialogTitle>Edit Session</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Session Name"
            fullWidth
            variant="outlined"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialogOpen(false)}>Cancel</Button>
          <Button onClick={confirmEdit} variant="contained">
            Save
          </Button>
        </DialogActions>
      </Dialog>

      {/* Session Limit Dialog (OLD - kept as fallback) */}
      <Dialog open={limitDialogOpen} onClose={() => setLimitDialogOpen(false)}>
        <DialogTitle>Session Limit Reached</DialogTitle>
        <DialogContent>
          <Typography>
            You have reached the maximum of {maxSessions} sessions. Please delete an existing session to create a new one.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setLimitDialogOpen(false)} variant="contained">
            OK
          </Button>
        </DialogActions>
      </Dialog>

      {/* Auto-Delete Oldest Confirmation Dialog */}
      <Dialog open={deleteOldestDialogOpen} onClose={() => setDeleteOldestDialogOpen(false)}>
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'warning.main' }}>
          <AlertCircle size={24} />
          Session Limit Reached
        </DialogTitle>
        <DialogContent>
          <Typography paragraph>
            You have reached the limit of <strong>{maxSessions} chats</strong>.
          </Typography>
          <Typography variant="body2" color="text.secondary">
            To create a new chat, we need to delete your oldest session:
          </Typography>
          <Box sx={{ mt: 2, p: 2, bgcolor: 'action.hover', borderRadius: 1, border: '1px dashed', borderColor: 'divider' }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
              {oldestSession?.name || 'Oldest Session'}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Last active: {oldestSession?.last_activity ? new Date(oldestSession.last_activity).toLocaleDateString() : 'Unknown'}
            </Typography>
          </Box>
          <Typography sx={{ mt: 2 }}>
            Do you want to delete this chat and proceed?
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteOldestDialogOpen(false)}>Cancel</Button>
          <Button onClick={confirmDeleteOldest} variant="contained" color="warning">
            Delete & Create New
          </Button>
        </DialogActions>
      </Dialog>

      {/* Debug Info */}
      {/* <Box sx={{ position: 'fixed', bottom: 4, right: 4, opacity: 0.3, fontSize: '10px', pointerEvents: 'none' }}>
        UID: {userId}
      </Box> */}
    </>
  );
}
