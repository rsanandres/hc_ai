import { Box, Typography, Button, Card, CardContent, Stack, Divider } from '@mui/material';
import { FileText, ExternalLink, BookOpen, Code, Database, Cloud } from 'lucide-react';
import { alpha } from '@mui/material/styles';

export function DocumentationPanel() {
    const handleOpenDocs = () => {
        // Navigate to the documentation viewer page
        window.open('/docs', '_blank');
    };

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, p: 2, pb: 4 }}>
            {/* Header Card */}
            <Card
                variant="outlined"
                sx={{
                    bgcolor: (theme) => alpha(theme.palette.primary.main, 0.05),
                    borderColor: 'primary.main',
                }}
            >
                <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
                        <Box
                            sx={{
                                width: 48,
                                height: 48,
                                borderRadius: 2,
                                bgcolor: 'primary.main',
                                color: 'primary.contrastText',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                            }}
                        >
                            <BookOpen size={24} />
                        </Box>
                        <Box sx={{ flex: 1 }}>
                            <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                                Technical Documentation
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                                Comprehensive technical documentation showcasing the architecture, design, and implementation of the Atlas Healthcare RAG system.
                            </Typography>
                        </Box>
                    </Box>
                </CardContent>
            </Card>

            <Divider />

            {/* Documentation Sections Preview */}
            <Box>
                <Typography variant="subtitle2" sx={{ mb: 1.5, color: 'text.secondary', fontWeight: 600 }}>
                    📚 Documentation Contents
                </Typography>
                <Stack spacing={1}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, pl: 1 }}>
                        <Code size={14} color="#888" />
                        <Typography variant="caption">System Overview & Architecture</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, pl: 1 }}>
                        <Code size={14} color="#888" />
                        <Typography variant="caption">Data Ingestion & Processing Pipeline</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, pl: 1 }}>
                        <Database size={14} color="#888" />
                        <Typography variant="caption">Vector Storage & Retrieval</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, pl: 1 }}>
                        <Code size={14} color="#888" />
                        <Typography variant="caption">Agent System & LangGraph</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, pl: 1 }}>
                        <Cloud size={14} color="#888" />
                        <Typography variant="caption">AWS Migration Plan</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, pl: 1 }}>
                        <FileText size={14} color="#888" />
                        <Typography variant="caption">And 5 more sections...</Typography>
                    </Box>
                </Stack>
            </Box>

            <Divider />

            {/* Open Button */}
            <Button
                variant="contained"
                size="large"
                onClick={handleOpenDocs}
                startIcon={<FileText size={18} />}
                endIcon={<ExternalLink size={16} />}
                sx={{
                    py: 1.5,
                    borderRadius: 2,
                    textTransform: 'none',
                    fontWeight: 600,
                    background: (theme) =>
                        `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)`,
                    boxShadow: 2,
                    '&:hover': {
                        boxShadow: 4,
                        transform: 'translateY(-1px)',
                        transition: 'all 0.2s'
                    }
                }}
            >
                Open Technical Documentation
            </Button>

            {/* Info Box */}
            <Card variant="outlined" sx={{ bgcolor: (theme) => alpha(theme.palette.info.main, 0.05) }}>
                <CardContent>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                        💡 <strong>What&apos;s Inside:</strong>
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                        • Architecture diagrams (Local & AWS)<br />
                        • Implementation details and code examples<br />
                        • Performance benchmarks and metrics<br />
                        • Cost analysis and optimization strategies<br />
                        • Production-ready patterns and best practices
                    </Typography>
                </CardContent>
            </Card>
        </Box>
    );
}
