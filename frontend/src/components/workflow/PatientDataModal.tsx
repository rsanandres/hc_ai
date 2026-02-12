'use client';

import { useState } from 'react';
import { Box, Typography, Card, CardContent, Chip, IconButton, Stack, Dialog, DialogTitle, DialogContent, Tabs, Tab, List, ListItem, ListItemText, TextField } from '@mui/material';
import { Activity, ClipboardList, FileJson, X, Pill, Stethoscope, Calendar, Thermometer } from 'lucide-react';
import { alpha } from '@mui/material/styles';
import dynamic from 'next/dynamic';
import { getConditions, getMedications, getAllergies, getEncounters, getObservations, getImmunizations, getProcedures, getCarePlans } from '../../utils/fhirUtils';

const JsonView = dynamic(() => import('@microlink/react-json-view'), { ssr: false });

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type FhirBundle = any;

interface PatientDataModalProps {
  open: boolean;
  onClose: () => void;
  data: FhirBundle | null;
  patientName?: string;
}

export function PatientDataModal({ open, onClose, data, patientName }: PatientDataModalProps) {
  const [modalTab, setModalTab] = useState(0);
  const [sortOrder, setSortOrder] = useState<'default' | 'newest' | 'oldest'>('default');

  const summaryData = data ? {
    conditions: getConditions(data),
    medications: getMedications(data),
    allergies: getAllergies(data),
    encounters: getEncounters(data),
    observations: getObservations(data),
    immunizations: getImmunizations(data),
    procedures: getProcedures(data),
    carePlans: getCarePlans(data),
  } : null;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: { height: '90vh', display: 'flex', flexDirection: 'column' },
      }}
    >
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pb: 0 }}>
        <Box component="span" sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          Patient Data Viewer
          {patientName && (
            <Chip label={patientName} size="small" color="primary" variant="outlined" />
          )}
        </Box>
        <IconButton size="small" onClick={onClose}>
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
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: 3 }}>
              {/* Conditions */}
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

              {/* Medications */}
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

              {/* Vitals & Observations */}
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

              {/* Procedures & Immunizations */}
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

              {/* Encounters */}
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

        {modalTab === 1 && data?.entry && (
          <Box sx={{ p: 3, height: '100%', overflow: 'auto', bgcolor: 'background.default' }}>
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
              <TextField
                select
                size="small"
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value as 'default' | 'newest' | 'oldest')}
                SelectProps={{ native: true }}
                sx={{ minWidth: 200 }}
              >
                <option value="default">Default Order</option>
                <option value="newest">Newest First</option>
                <option value="oldest">Oldest First</option>
              </TextField>
            </Box>
            <Stack spacing={2}>
              {data.entry
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                .map((entry: any) => {
                  const r = entry.resource;
                  const type = r.resourceType;
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

                  if (date) dateObj = new Date(date);
                  return { entry, type, primary, secondary, date, dateObj };
                })
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                .sort((a: any, b: any) => {
                  if (sortOrder === 'default') return 0;
                  if (!a.dateObj && !b.dateObj) return 0;
                  if (!a.dateObj) return 1;
                  if (!b.dateObj) return -1;
                  return sortOrder === 'newest'
                    ? b.dateObj.getTime() - a.dateObj.getTime()
                    : a.dateObj.getTime() - b.dateObj.getTime();
                })
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
                          fontSize: '0.7rem',
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

        {modalTab === 2 && data && (
          <Box sx={{ height: '100%', overflow: 'auto', display: 'flex', flexDirection: 'column', bgcolor: '#1e1e1e' }}>
            <JsonView
              src={data}
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
  );
}
