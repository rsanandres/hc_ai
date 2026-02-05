import { useState } from 'react';
import { Box, Typography, Card, CardContent, Chip, IconButton, Button, Stack, Tooltip, Dialog, DialogTitle, DialogContent, DialogActions, Tabs, Tab, List, ListItem, ListItemText, Divider, CardActionArea, Grid, TextField } from '@mui/material';
import { Copy, User, Activity, AlertCircle, MessageSquare, FileText, FileJson, X, Pill, Stethoscope, Calendar, Thermometer, Syringe, ClipboardList, Microscope } from 'lucide-react';
import { alpha } from '@mui/material/styles';
import dynamic from 'next/dynamic';

// Import Persona Data
import larsonJson from '../../data/personas/larson.json';
import ziemeJson from '../../data/personas/zieme.json';
import christiansenJson from '../../data/personas/christiansen.json';
import hegmannJson from '../../data/personas/hegmann.json';
import herzogJson from '../../data/personas/herzog.json';
import adamJson from '../../data/personas/abbott_adam.json';
import alvaJson from '../../data/personas/abbott_alva.json';
import amayaJson from '../../data/personas/abbott_amaya.json';

// Import Utils
import { getConditions, getMedications, getAllergies, getEncounters, getObservations, getImmunizations, getProcedures, getCarePlans } from '../../utils/fhirUtils';

const JsonView = dynamic(() => import('@microlink/react-json-view'), { ssr: false });

const PERSONAS = [
    {
        name: "Danial Larson", // Cleaned name
        id: "5e81d5b2-af01-4367-9b2e-0cdf479094a4",
        age: 65,
        conditions: ["Recurrent rectal polyp", "Hypertension", "Chronic kidney disease"],
        description: "Older male with multiple chronic conditions.",
        data: larsonJson
    },
    {
        name: "Ron Zieme", // Cleaned name
        id: "d8d9460b-4cb6-47f9-a94f-9e58390204b2",
        age: 86,
        conditions: ["Hypertension", "Fibromyalgia", "Osteoporosis", "Coronary Heart Disease"],
        description: "Elderly female with complex history including MI and heart disease.",
        data: ziemeJson
    },
    {
        name: "Doug Christiansen", // Cleaned name
        id: "0beb6802-3353-4144-8ae3-97176bce86c3",
        age: 24,
        conditions: ["Chronic sinusitis"],
        description: "Young adult with chronic sinus issues.",
        data: christiansenJson
    },
    {
        name: "Jamie Hegmann", // Cleaned name
        id: "6a4168a1-2cfd-4269-8139-8a4a663adfe7",
        age: 71,
        conditions: ["Coronary Heart Disease", "Myocardial Infarction History"],
        description: "Female patient with significant cardiac history.",
        data: hegmannJson
    },
    {
        name: "Carlo Herzog", // Cleaned name
        id: "7f7ad77a-5dd5-4df0-ba36-f4f1e4b6d368",
        age: 23,
        conditions: ["Childhood asthma", "Allergic rhinitis", "Nut allergy"],
        description: "Young male with multiple allergies and asthma.",
        data: herzogJson
    },
    {
        name: "Adam Abbott",
        id: "53fcaff1-eb44-4257-819b-50b47f311edf",
        age: 31,
        conditions: ["Normal Pregnancy"],
        description: "Young female with active pregnancy.",
        data: adamJson
    },
    {
        name: "Alva Abbott",
        id: "f883318e-9a81-4f77-9cff-5318a00b777f",
        age: 67,
        conditions: ["Prediabetes"],
        description: "Older male managing prediabetes.",
        data: alvaJson
    },
    {
        name: "Amaya Abbott",
        id: "4b7098a8-13b8-4916-a379-6ae2c8a70a8a",
        age: 69,
        conditions: ["Hypertension", "Chronic sinusitis", "Concussion History"],
        description: "Older male with hypertension and history of head injury.",
        data: amayaJson
    }
];

const RECOMMENDED_PROMPTS = [
    "What are the patient's active conditions?",
    "Summarize the patient's medication history.",
    "Show me the timeline of recent encounters.",
    "Does the patient have any known allergies?"
];

// Patient type for selection
interface SelectedPatient {
    id: string;
    name: string;
}

interface ReferencePanelProps {
    onCopy: (text: string) => void;
    onPromptSelect?: (text: string) => void;
    selectedPatient?: SelectedPatient | null;
    onPatientSelect?: (patient: SelectedPatient | null) => void;
}

export function ReferencePanel({ onCopy, onPromptSelect, selectedPatient, onPatientSelect }: ReferencePanelProps) {
    const [modalOpen, setModalOpen] = useState(false);
    const [modalTab, setModalTab] = useState(0);
    const [selectedJson, setSelectedJson] = useState<any>(null);
    const [sortOrder, setSortOrder] = useState<'default' | 'newest' | 'oldest'>('default');

    const handleCopy = (text: string, label: string) => {
        navigator.clipboard.writeText(text);
        onCopy(`Copied ${label}`);
    };

    const handlePromptClick = (prompt: string) => {
        if (onPromptSelect) {
            // Just insert the prompt directly - patient is already selected
            onPromptSelect(prompt);
        } else {
            handleCopy(prompt, "Prompt");
        }
    };

    const handleOpenModal = (data: any) => {
        setSelectedJson(data);
        setModalTab(0); // Default to summary
    };

    // Derived data for summary view
    const summaryData = selectedJson ? {
        conditions: getConditions(selectedJson),
        medications: getMedications(selectedJson),
        allergies: getAllergies(selectedJson),
        encounters: getEncounters(selectedJson),
        observations: getObservations(selectedJson),
        immunizations: getImmunizations(selectedJson),
        procedures: getProcedures(selectedJson),
        carePlans: getCarePlans(selectedJson)
    } : null;

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, p: 2, pb: 4 }}>

            {/* Prompts Section (Moved to Top) */}
            <Box>
                <Typography variant="subtitle2" sx={{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 1, color: 'text.secondary', fontWeight: 600 }}>
                    <MessageSquare size={16} />
                    Recommended Prompts
                </Typography>
                <Stack spacing={1}>
                    {RECOMMENDED_PROMPTS.map((prompt, i) => (
                        <Button
                            key={i}
                            variant="outlined"
                            size="small"
                            onClick={() => handlePromptClick(prompt)}
                            sx={{
                                justifyContent: 'flex-start',
                                textAlign: 'left',
                                textTransform: 'none',
                                borderColor: 'divider',
                                color: 'text.primary',
                                py: 1,
                                '&:hover': {
                                    bgcolor: 'action.hover',
                                    borderColor: 'primary.main'
                                }
                            }}
                            endIcon={<Copy size={14} style={{ marginLeft: 'auto', opacity: 0.5 }} />}
                        >
                            {prompt}
                        </Button>
                    ))}
                </Stack>
            </Box>

            <Divider />

            {/* Personas Section */}
            <Box>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
                    <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'text.secondary', fontWeight: 600 }}>
                        <User size={16} />
                        {selectedPatient ? 'Selected Patient' : 'Select a Patient'}
                    </Typography>
                    {selectedPatient && onPatientSelect && (
                        <Button
                            size="small"
                            variant="text"
                            onClick={() => onPatientSelect(null)}
                            sx={{ fontSize: '0.7rem', minWidth: 'auto', p: 0.5 }}
                        >
                            Clear
                        </Button>
                    )}
                </Box>
                {selectedPatient && (
                    <Chip
                        label={`Active: ${selectedPatient.name}`}
                        color="primary"
                        size="small"
                        sx={{ mb: 1.5, fontWeight: 600 }}
                    />
                )}
                <Stack spacing={2}>
                    {PERSONAS.map((p) => {
                        const isSelected = selectedPatient?.id === p.id;
                        return (
                        <Card
                            key={p.id}
                            variant="outlined"
                            sx={{
                                bgcolor: (theme) => isSelected
                                    ? alpha(theme.palette.primary.main, 0.15)
                                    : alpha(theme.palette.background.paper, 0.4),
                                backdropFilter: 'blur(10px)',
                                borderColor: isSelected ? 'primary.main' : 'divider',
                                borderWidth: isSelected ? 2 : 1,
                                transition: 'all 0.2s',
                                '&:hover': {
                                    bgcolor: (theme) => isSelected
                                        ? alpha(theme.palette.primary.main, 0.2)
                                        : alpha(theme.palette.background.paper, 0.6),
                                    borderColor: 'primary.main',
                                    transform: 'translateY(-2px)',
                                    boxShadow: 2
                                },
                                cursor: 'pointer',
                                position: 'relative'
                            }}
                        >
                            {/* Copy Button - Positioned absolutely to avoid nesting in CardActionArea */}
                            <Box
                                sx={{
                                    position: 'absolute',
                                    top: 12,
                                    right: 12,
                                    zIndex: 1
                                }}
                                onClick={(e) => e.stopPropagation()}
                            >
                                <Tooltip title="Copy Patient ID">
                                    <IconButton
                                        size="small"
                                        onClick={() => handleCopy(p.id, "Patient ID")}
                                        sx={{
                                            bgcolor: 'background.paper',
                                            '&:hover': {
                                                bgcolor: 'action.hover'
                                            }
                                        }}
                                    >
                                        <Copy size={14} />
                                    </IconButton>
                                </Tooltip>
                            </Box>

                            <CardActionArea
                                onClick={() => {
                                    // Primary action: select patient for queries
                                    if (onPatientSelect) {
                                        onPatientSelect(isSelected ? null : { id: p.id, name: p.name });
                                    } else {
                                        // Fallback: open modal if no selection handler
                                        handleOpenModal(p.data);
                                    }
                                }}
                                sx={{ p: 1.5, pr: 6 }}
                            >
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                                    <Box>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <Typography variant="subtitle2" fontWeight="bold">
                                                {p.name}
                                            </Typography>
                                            {isSelected && (
                                                <Chip
                                                    label="Selected"
                                                    size="small"
                                                    color="primary"
                                                    sx={{ height: 18, fontSize: '0.6rem' }}
                                                />
                                            )}
                                        </Box>
                                        <Typography variant="caption" color="text.secondary">
                                            {p.age} years old • {p.description}
                                        </Typography>
                                    </Box>
                                </Box>

                                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mt: 1 }}>
                                    {p.conditions.slice(0, 3).map((c, i) => (
                                        <Chip
                                            key={i}
                                            label={c}
                                            size="small"
                                            sx={{ height: 20, fontSize: '0.65rem' }}
                                        />
                                    ))}
                                    {p.conditions.length > 3 && (
                                        <Chip label={`+${p.conditions.length - 3}`} size="small" sx={{ height: 20, fontSize: '0.65rem' }} />
                                    )}
                                </Box>

                                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 1.5 }}>
                                    <Typography
                                        variant="caption"
                                        sx={{
                                            fontFamily: 'monospace',
                                            bgcolor: 'action.hover',
                                            p: 0.5,
                                            borderRadius: 1,
                                            fontSize: '0.65rem',
                                            wordBreak: 'break-all',
                                            flex: 1
                                        }}
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleCopy(p.id, "ID");
                                        }}
                                    >
                                        ID: {p.id}
                                    </Typography>
                                    <Typography
                                        variant="caption"
                                        component="span"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleOpenModal(p.data);
                                        }}
                                        sx={{
                                            fontSize: '0.65rem',
                                            ml: 1,
                                            color: 'primary.main',
                                            cursor: 'pointer',
                                            '&:hover': {
                                                textDecoration: 'underline'
                                            }
                                        }}
                                    >
                                        View Data
                                    </Typography>
                                </Box>
                            </CardActionArea>
                        </Card>
                    );
                    })}
                </Stack>
            </Box>

            {/* Patient Details Modal */}
            <Dialog
                open={!!selectedJson}
                onClose={() => setSelectedJson(null)}
                maxWidth="lg"
                fullWidth
                PaperProps={{
                    sx: { height: '90vh', display: 'flex', flexDirection: 'column' }
                }}
            >
                <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pb: 0 }}>
                    <Box component="span" sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        Patient Data Viewer
                        {selectedJson && (
                            <Chip
                                label={PERSONAS.find(p => p.data === selectedJson)?.name || 'Unknown Patient'}
                                size="small"
                                color="primary"
                                variant="outlined"
                            />
                        )}
                    </Box>
                    <IconButton size="small" onClick={() => setSelectedJson(null)}>
                        <X size={20} />
                    </IconButton>
                </DialogTitle>

                <Box sx={{ borderBottom: 1, borderColor: 'divider', px: 3 }}>
                    <Tabs value={modalTab} onChange={(_, v) => setModalTab(v)}>
                        <Tab icon={<Activity size={16} />} iconPosition="start" label="Detailed Summary" />
                        <Tab icon={<ClipboardList size={16} />} iconPosition="start" label="All Entries" />
                        <Tab icon={<FileJson size={16} />} iconPosition="start" label="Raw JSON" />
                    </Tabs>
                </Box>

                <DialogContent sx={{ p: 0, flex: 1, overflow: 'hidden', bgcolor: 'background.default' }}>
                    {modalTab === 0 && summaryData && (
                        <Box sx={{ p: 3, height: '100%', overflow: 'auto' }}>
                            {/* Masonry-like Grid */}
                            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: 3 }}>

                                {/* 1. Conditions */}
                                <Card variant="outlined">
                                    <CardContent>
                                        <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2, color: 'error.main' }}>
                                            <Activity size={18} /> Active Conditions
                                        </Typography>
                                        {summaryData.conditions.length > 0 ? (
                                            <Stack spacing={1}>
                                                {summaryData.conditions.map((c, i) => (
                                                    <Box key={i} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                        <Typography variant="body2" fontWeight={500}>{c.name}</Typography>
                                                        <Chip label={c.status} size="small" color="error" variant="outlined" sx={{ height: 20, fontSize: '0.7rem' }} />
                                                    </Box>
                                                ))}
                                            </Stack>
                                        ) : <Typography variant="caption" color="text.secondary">No active conditions found</Typography>}
                                    </CardContent>
                                </Card>

                                {/* 2. Medications */}
                                <Card variant="outlined">
                                    <CardContent>
                                        <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2, color: 'primary.main' }}>
                                            <Pill size={18} /> Medications
                                        </Typography>
                                        {summaryData.medications.length > 0 ? (
                                            <Stack spacing={1.5}>
                                                {summaryData.medications.map((m, i) => (
                                                    <Box key={i} sx={{ p: 1, bgcolor: 'action.hover', borderRadius: 1 }}>
                                                        <Typography variant="body2" fontWeight={500}>{m.name}</Typography>
                                                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
                                                            <Typography variant="caption" color="text.secondary">Status: {m.status}</Typography>
                                                            {m.authoredOn && <Typography variant="caption" color="text.secondary">{new Date(m.authoredOn).toLocaleDateString()}</Typography>}
                                                        </Box>
                                                    </Box>
                                                ))}
                                            </Stack>
                                        ) : <Typography variant="caption" color="text.secondary">No active medications found</Typography>}
                                    </CardContent>
                                </Card>

                                {/* 3. Vitals & Observations (New) */}
                                <Card variant="outlined" sx={{ gridRow: 'span 2' }}>
                                    <CardContent>
                                        <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2, color: 'info.main' }}>
                                            <Thermometer size={18} /> Vitals & Labs ({summaryData.observations.length})
                                        </Typography>
                                        {summaryData.observations.length > 0 ? (
                                            <List dense disablePadding sx={{ maxHeight: 400, overflow: 'auto' }}>
                                                {summaryData.observations.slice(0, 15).map((o, i) => (
                                                    <ListItem key={i} divider disableGutters>
                                                        <ListItemText
                                                            primary={<Typography variant="body2">{o.name}</Typography>}
                                                            secondary={
                                                                <Box component="span" sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
                                                                    <Typography variant="body2" component="span" fontWeight="bold" color="text.primary">{o.value}</Typography>
                                                                    <Typography variant="caption" component="span">{o.date ? new Date(o.date).toLocaleDateString() : ''}</Typography>
                                                                </Box>
                                                            }
                                                        />
                                                    </ListItem>
                                                ))}
                                                {summaryData.observations.length > 15 && (
                                                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', pt: 1, textAlign: 'center' }}>
                                                        +{summaryData.observations.length - 15} more observations
                                                    </Typography>
                                                )}
                                            </List>
                                        ) : <Typography variant="caption" color="text.secondary">No observations found</Typography>}
                                    </CardContent>
                                </Card>

                                {/* 4. Procedures & Immunizations (New) */}
                                <Card variant="outlined">
                                    <CardContent>
                                        <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2, color: 'warning.main' }}>
                                            <Stethoscope size={18} /> Procedures & History
                                        </Typography>
                                        <Stack spacing={2}>
                                            {summaryData.procedures.length > 0 && (
                                                <Box>
                                                    <Typography variant="caption" fontWeight="bold" color="text.secondary" sx={{ mb: 1, display: 'block' }}>PROCEDURES</Typography>
                                                    <Stack spacing={0.5}>
                                                        {summaryData.procedures.slice(0, 3).map((p, i) => (
                                                            <Box key={i} sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                                                <Typography variant="caption" sx={{ flex: 1 }}>{p.name}</Typography>
                                                                <Typography variant="caption" color="text.secondary">{p.date ? new Date(p.date).toLocaleDateString() : ''}</Typography>
                                                            </Box>
                                                        ))}
                                                    </Stack>
                                                </Box>
                                            )}

                                            {summaryData.immunizations.length > 0 && (
                                                <Box>
                                                    <Typography variant="caption" fontWeight="bold" color="text.secondary" sx={{ mb: 1, display: 'block' }}>IMMUNIZATIONS</Typography>
                                                    <Stack spacing={0.5}>
                                                        {summaryData.immunizations.slice(0, 3).map((im, i) => (
                                                            <Box key={i} sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                                                <Typography variant="caption" sx={{ flex: 1 }}>{im.vaccine}</Typography>
                                                                <Typography variant="caption" color="text.secondary">{im.date ? new Date(im.date).toLocaleDateString() : ''}</Typography>
                                                            </Box>
                                                        ))}
                                                    </Stack>
                                                </Box>
                                            )}

                                            {summaryData.procedures.length === 0 && summaryData.immunizations.length === 0 && (
                                                <Typography variant="caption" color="text.secondary">No procedures or immunizations found</Typography>
                                            )}
                                        </Stack>
                                    </CardContent>
                                </Card>

                                {/* 5. Encounters */}
                                <Card variant="outlined">
                                    <CardContent>
                                        <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                                            <Calendar size={18} /> Recent Encounters
                                        </Typography>
                                        <List dense disablePadding>
                                            {summaryData.encounters.length > 0 ? summaryData.encounters.map((e, i) => (
                                                <ListItem key={i} divider={i !== summaryData.encounters.length - 1} disableGutters>
                                                    <ListItemText
                                                        primary={e.type}
                                                        secondary={
                                                            <Box component="span" sx={{ display: 'flex', gap: 2 }}>
                                                                <span>{e.period ? new Date(e.period).toLocaleDateString() : 'Unknown Date'}</span>
                                                                {e.reason && <span>Reason: {e.reason}</span>}
                                                            </Box>
                                                        }
                                                    />
                                                </ListItem>
                                            )) : <Typography variant="caption" color="text.secondary">No recent encounters found</Typography>}
                                        </List>
                                    </CardContent>
                                </Card>
                            </Box>
                        </Box>
                    )}

                    {modalTab === 1 && selectedJson?.entry && (
                        <Box sx={{ p: 3, height: '100%', overflow: 'auto', bgcolor: 'background.default' }}>
                            <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
                                <TextField
                                    select
                                    size="small"
                                    value={sortOrder}
                                    onChange={(e) => setSortOrder(e.target.value as any)}
                                    SelectProps={{ native: true }}
                                    sx={{ minWidth: 200 }}
                                >
                                    <option value="default">Default Order</option>
                                    <option value="newest">Newest First</option>
                                    <option value="oldest">Oldest First</option>
                                </TextField>
                            </Box>
                            <Stack spacing={2}>
                                {selectedJson.entry
                                    .map((entry: any) => {
                                        const r = entry.resource;
                                        const type = r.resourceType;

                                        // Helper to get primary display text
                                        let primary = 'Unknown Resource';
                                        let secondary = '';
                                        let date = '';
                                        let dateObj: Date | null = null;

                                        if (type === 'Patient') {
                                            primary = `${r.name?.[0]?.given?.join(' ')} ${r.name?.[0]?.family}`;
                                            secondary = `${r.gender}, DOB: ${r.birthDate}`;
                                        } else if (type === 'Encounter') {
                                            primary = r.type?.[0]?.text || r.type?.[0]?.coding?.[0]?.display || 'Visit';
                                            secondary = r.reasonCode?.[0]?.text || r.reasonCode?.[0]?.coding?.[0]?.display || '';
                                            date = r.period?.start;
                                        } else if (type === 'Condition') {
                                            primary = r.code?.text || r.code?.coding?.[0]?.display;
                                            secondary = r.clinicalStatus?.coding?.[0]?.code;
                                            date = r.onsetDateTime;
                                        } else if (type === 'Observation') {
                                            primary = r.code?.text || r.code?.coding?.[0]?.display;
                                            if (r.valueQuantity) secondary = `${parseFloat(r.valueQuantity.value).toFixed(1)} ${r.valueQuantity.unit || ''}`;
                                            else if (r.valueCodeableConcept) secondary = r.valueCodeableConcept.text;
                                            else if (r.component) secondary = 'Multi-component observation';
                                            date = r.effectiveDateTime;
                                        } else if (type === 'MedicationRequest') {
                                            primary = r.medicationCodeableConcept?.text || r.medicationCodeableConcept?.coding?.[0]?.display;
                                            secondary = r.status;
                                            date = r.authoredOn;
                                        } else if (type === 'Procedure') {
                                            primary = r.code?.text || r.code?.coding?.[0]?.display;
                                            secondary = r.status;
                                            date = r.performedDateTime || r.performedPeriod?.start;
                                        } else if (type === 'Immunization') {
                                            primary = r.vaccineCode?.text || r.vaccineCode?.coding?.[0]?.display;
                                            secondary = r.status;
                                            date = r.occurrenceDateTime;
                                        } else {
                                            primary = type;
                                            secondary = r.id;
                                        }

                                        if (date) {
                                            dateObj = new Date(date);
                                        }

                                        return { entry, type, primary, secondary, date, dateObj };
                                    })
                                    .sort((a: any, b: any) => {
                                        if (sortOrder === 'default') return 0;
                                        if (!a.dateObj && !b.dateObj) return 0;
                                        if (!a.dateObj) return 1;
                                        if (!b.dateObj) return -1;

                                        return sortOrder === 'newest'
                                            ? b.dateObj.getTime() - a.dateObj.getTime()
                                            : a.dateObj.getTime() - b.dateObj.getTime();
                                    })
                                    .map((item: any, i: number) => (
                                        <Card key={i} variant="outlined" sx={{ borderRadius: 3, '&:hover': { borderColor: 'primary.main', bgcolor: 'action.hover' } }}>
                                            <CardContent sx={{ p: '16px !important', display: 'flex', alignItems: 'center', gap: 2 }}>
                                                <Chip
                                                    label={item.type}
                                                    size="small"
                                                    sx={{
                                                        minWidth: 100,
                                                        bgcolor: (theme) => alpha(theme.palette.primary.main, 0.1),
                                                        color: 'primary.main',
                                                        fontWeight: 600,
                                                        fontSize: '0.7rem'
                                                    }}
                                                />
                                                <Box sx={{ flex: 1 }}>
                                                    <Typography variant="body2" fontWeight="bold">{item.primary}</Typography>
                                                    {item.secondary && <Typography variant="caption" color="text.secondary">{item.secondary}</Typography>}
                                                </Box>
                                                {item.date && (
                                                    <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
                                                        {new Date(item.date).toLocaleDateString()}
                                                    </Typography>
                                                )}
                                            </CardContent>
                                        </Card>
                                    ))}
                            </Stack>
                        </Box>
                    )}

                    {modalTab === 2 && (
                        <Box sx={{ height: '100%', overflow: 'auto', display: 'flex', flexDirection: 'column', bgcolor: '#1e1e1e' }}>
                            <JsonView
                                src={selectedJson}
                                theme="codeschool"
                                style={{ padding: '20px', fontFamily: 'monospace', fontSize: '0.85rem', backgroundColor: 'transparent' }}
                                displayDataTypes={false}
                                displayObjectSize={true}
                                enableClipboard={true}
                                collapsed={2}
                            />
                        </Box>
                    )}
                </DialogContent>
            </Dialog>
        </Box>
    );
}
