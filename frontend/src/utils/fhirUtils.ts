
// Lightweight FHIR types for untyped JSON parsing
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type FhirResource = Record<string, any>;

interface FhirEntry {
    resource?: FhirResource;
}

interface FhirBundle {
    entry?: FhirEntry[];
}

export interface ParsedCondition {
    name: string;
    status: string;
    onset?: string;
}

export interface ParsedMedication {
    name: string;
    status: string;
    authoredOn?: string;
}

export interface ParsedEncounter {
    type: string;
    period?: string;
    reason?: string;
}

export interface ParsedAllergy {
    substance: string;
    criticality?: string;
    reaction?: string;
}

export interface ParsedObservation {
    name: string;
    value: string;
    unit?: string;
    date?: string;
    category?: string;
}

export interface ParsedImmunization {
    vaccine: string;
    date: string;
    status: string;
}

export interface ParsedProcedure {
    name: string;
    date?: string;
    status: string;
}

export interface ParsedCarePlan {
    category: string;
    status: string;
    period?: string;
    goals?: string[];
}

export function getConditions(bundle: FhirBundle): ParsedCondition[] {
    if (!bundle?.entry) return [];

    return bundle.entry
        .filter((e: FhirEntry) => e.resource?.resourceType === 'Condition')
        .map((e: FhirEntry) => {
            const r = e.resource!;
            return {
                name: r.code?.text || r.code?.coding?.[0]?.display || 'Unknown Condition',
                status: (typeof r.clinicalStatus === 'string' ? r.clinicalStatus : r.clinicalStatus?.coding?.[0]?.code) || 'unknown',
                onset: r.onsetDateTime
            };
        })
        .filter((c: ParsedCondition) => c.status === 'active' || c.status === 'recurrence'); // Prioritize active
}

export function getMedications(bundle: FhirBundle): ParsedMedication[] {
    if (!bundle?.entry) return [];

    return bundle.entry
        .filter((e: FhirEntry) => e.resource?.resourceType === 'MedicationRequest')
        .map((e: FhirEntry) => {
            const r = e.resource!;
            return {
                name: r.medicationCodeableConcept?.text || r.medicationCodeableConcept?.coding?.[0]?.display || 'Unknown Medication',
                status: r.status || 'unknown',
                authoredOn: r.authoredOn
            };
        })
        .filter((m: ParsedMedication) => m.status === 'active');
}

export function getAllergies(bundle: FhirBundle): ParsedAllergy[] {
    if (!bundle?.entry) return [];

    return bundle.entry
        .filter((e: FhirEntry) => e.resource?.resourceType === 'AllergyIntolerance')
        .map((e: FhirEntry) => {
            const r = e.resource!;
            return {
                substance: r.code?.text || r.code?.coding?.[0]?.display || 'Unknown Substance',
                criticality: r.criticality,
                reaction: r.reaction?.[0]?.manifestation?.[0]?.text
            };
        });
}

export function getEncounters(bundle: FhirBundle): ParsedEncounter[] {
    if (!bundle?.entry) return [];

    const encounters = bundle.entry
        .filter((e: FhirEntry) => e.resource?.resourceType === 'Encounter')
        .map((e: FhirEntry) => {
            const r = e.resource!;
            return {
                type: r.type?.[0]?.text || r.type?.[0]?.coding?.[0]?.display || 'Visit',
                period: r.period?.start,
                reason: r.reasonCode?.[0]?.text || r.reasonCode?.[0]?.coding?.[0]?.display
            };
        });

    // Sort by date desc
    return encounters.sort((a: ParsedEncounter, b: ParsedEncounter) => {
        return new Date(b.period || 0).getTime() - new Date(a.period || 0).getTime();
    }).slice(0, 5); // Just latest 5
}

export function getObservations(bundle: FhirBundle): ParsedObservation[] {
    if (!bundle?.entry) return [];

    return bundle.entry
        .filter((e: FhirEntry) => e.resource?.resourceType === 'Observation')
        .map((e: FhirEntry) => {
            const r = e.resource!;
            let val = 'N/A';
            if (r.valueQuantity) {
                val = `${parseFloat(r.valueQuantity.value).toFixed(1)} ${r.valueQuantity.unit || ''}`;
            } else if (r.valueCodeableConcept) {
                val = r.valueCodeableConcept.text || r.valueCodeableConcept.coding?.[0]?.display;
            } else if (r.valueString) {
                val = r.valueString;
            } else if (r.component) {
                // For BP usually
                val = r.component.map((c: FhirResource) => {
                    const code = c.code?.coding?.[0]?.display || c.code?.text;
                    const v = c.valueQuantity ? `${c.valueQuantity.value}` : '';
                    return `${v} (${code})`;
                }).join(' / ');
            }

            return {
                name: r.code?.text || r.code?.coding?.[0]?.display || 'Unknown Observation',
                value: val,
                date: r.effectiveDateTime,
                category: r.category?.[0]?.coding?.[0]?.display || 'General'
            };
        })
        .sort((a: ParsedObservation, b: ParsedObservation) => new Date(b.date || 0).getTime() - new Date(a.date || 0).getTime());
}

export function getImmunizations(bundle: FhirBundle): ParsedImmunization[] {
    if (!bundle?.entry) return [];

    return bundle.entry
        .filter((e: FhirEntry) => e.resource?.resourceType === 'Immunization')
        .map((e: FhirEntry) => {
            const r = e.resource!;
            return {
                vaccine: r.vaccineCode?.text || r.vaccineCode?.coding?.[0]?.display || 'Unknown Vaccine',
                date: r.occurrenceDateTime,
                status: r.status
            };
        })
        .sort((a: ParsedImmunization, b: ParsedImmunization) => new Date(b.date).getTime() - new Date(a.date).getTime());
}

export function getProcedures(bundle: FhirBundle): ParsedProcedure[] {
    if (!bundle?.entry) return [];

    return bundle.entry
        .filter((e: FhirEntry) => e.resource?.resourceType === 'Procedure')
        .map((e: FhirEntry) => {
            const r = e.resource!;
            return {
                name: r.code?.text || r.code?.coding?.[0]?.display || 'Unknown Procedure',
                date: r.performedDateTime || r.performedPeriod?.start,
                status: r.status
            };
        })
        .sort((a: ParsedProcedure, b: ParsedProcedure) => new Date(b.date || 0).getTime() - new Date(a.date || 0).getTime());
}

export function getCarePlans(bundle: FhirBundle): ParsedCarePlan[] {
    if (!bundle?.entry) return [];

    return bundle.entry
        .filter((e: FhirEntry) => e.resource?.resourceType === 'CarePlan')
        .map((e: FhirEntry) => {
            const r = e.resource!;
            return {
                category: r.category?.[0]?.text || r.category?.[0]?.coding?.[0]?.display || 'General Care Plan',
                status: r.status,
                period: r.period?.start,
                goals: [] // Goals are references, complexity to resolve might be needed if strictly requested, but text summary is usually in category
            };
        });
}
