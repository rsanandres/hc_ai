'use client';

import { Box, Typography, Stack, Button } from '@mui/material';
import { MessageSquare } from 'lucide-react';

interface RecommendedPromptsProps {
  prompts: string[];
  onPromptClick: (prompt: string) => void;
}

export function RecommendedPrompts({ prompts, onPromptClick }: RecommendedPromptsProps) {
  return (
    <Box>
      <Typography variant="subtitle2" sx={{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 1, color: 'text.secondary', fontWeight: 600 }}>
        <MessageSquare size={16} />
        Step 2: Ask a Recommended Question
      </Typography>
      <Stack spacing={1}>
        {prompts.map((prompt, i) => (
          <Button
            key={i}
            variant="outlined"
            size="small"
            onClick={() => onPromptClick(prompt)}
            sx={{
              justifyContent: 'flex-start',
              textAlign: 'left',
              textTransform: 'none',
              borderColor: 'divider',
              color: 'text.primary',
              py: 1,
              '&:hover': {
                bgcolor: 'action.hover',
                borderColor: 'primary.main',
              },
            }}
          >
            {prompt}
          </Button>
        ))}
      </Stack>
    </Box>
  );
}
