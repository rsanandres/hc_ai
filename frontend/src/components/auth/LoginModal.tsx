import React, { useState } from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    TextField,
    Typography,
    Box,
    Alert
} from '@mui/material';
import { User, KeyRound } from 'lucide-react';

interface LoginModalProps {
    open: boolean;
    onClose: () => void;
    onLogin: (userId: string) => void;
    currentUserId: string;
}

export function LoginModal({ open, onClose, onLogin, currentUserId }: LoginModalProps) {
    const [username, setUsername] = useState('');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (username.trim()) {
            onLogin(username.trim());
            onClose();
        }
    };

    return (
        <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
            <form onSubmit={handleSubmit}>
                <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <User size={20} />
                    Login / Switch User
                </DialogTitle>
                <DialogContent>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
                        {currentUserId && (
                            <Alert severity="success" icon={<User size={18} />}>
                                <Typography variant="body2">
                                    Currently signed in as: <strong>{currentUserId}</strong>
                                </Typography>
                            </Alert>
                        )}

                        <Typography variant="body2" color="text.secondary">
                            Enter a username to identify yourself. This will allow you to access your sessions across devices.
                        </Typography>

                        <TextField
                            autoFocus
                            label="Username or User ID"
                            fullWidth
                            variant="outlined"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            placeholder="e.g. raph"
                            InputProps={{
                                startAdornment: <KeyRound size={16} style={{ marginRight: 8, opacity: 0.5 }} />
                            }}
                        />

                        <Alert severity="info" sx={{ mt: 1 }}>
                            <Typography variant="caption" display="block" gutterBottom>
                                <strong>Recover missing sessions:</strong>
                            </Typography>
                            <Typography variant="caption">
                                Try using ID: <code>178eb255</code>
                            </Typography>
                        </Alert>
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={onClose}>Cancel</Button>
                    <Button type="submit" variant="contained" disabled={!username.trim()}>
                        Login
                    </Button>
                </DialogActions>
            </form>
        </Dialog>
    );
}
