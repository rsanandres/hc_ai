// Shared patient metadata and prompts — used by WelcomeScreen and ReferencePanel

export interface FeaturedPatient {
  id: string;
  name: string;
  age: number;
  conditions: string[];
  description: string;
  chunks?: number;
}

// 6 original personas + 9 example patients = 15 featured patients
export const FEATURED_PATIENTS: FeaturedPatient[] = [
  // Original personas (have full FHIR bundles in /data/personas/)
  { id: "616d0449-c98e-46bb-a1f6-0170499fd4e4", name: "Hailee Kovacek", age: 52, conditions: ["Allergies", "Conditions", "Labs", "Procedures"], description: "375 records across 13 resource types.", chunks: 375 },
  { id: "0beb6802-3353-4144-8ae3-97176bce86c3", name: "Doug Christiansen", age: 24, conditions: ["Chronic sinusitis"], description: "Young adult with chronic sinus issues." },
  { id: "6a4168a1-2cfd-4269-8139-8a4a663adfe7", name: "Jamie Hegmann", age: 71, conditions: ["Coronary Heart Disease", "Myocardial Infarction History"], description: "Female patient with significant cardiac history." },
  { id: "7f7ad77a-5dd5-4df0-ba36-f4f1e4b6d368", name: "Carlo Herzog", age: 23, conditions: ["Childhood asthma", "Allergic rhinitis", "Nut allergy"], description: "Young male with multiple allergies and asthma." },
  { id: "53fcaff1-eb44-4257-819b-50b47f311edf", name: "Adam Abbott", age: 31, conditions: ["Normal Pregnancy"], description: "Young female with active pregnancy." },
  { id: "4b7098a8-13b8-4916-a379-6ae2c8a70a8a", name: "Amaya Abbott", age: 69, conditions: ["Hypertension", "Chronic sinusitis", "Concussion History"], description: "Older male with hypertension and history of head injury." },

  // Data-rich example patients (from example-patients.json)
  { id: "0c23c2f2-bd77-4311-a576-7829d807f2e2", name: "Pauline Weber", age: 67, conditions: ["Lung cancer", "COPD", "Prediabetes"], description: "Complex oncology and respiratory history.", chunks: 356 },
  { id: "a1d034a7-8e76-4b4c-806a-465bf66a0702", name: "Lela Tromp", age: 48, conditions: ["Diabetes", "Hypertension", "Diabetic retinopathy"], description: "Diabetes with complications, medications, and labs.", chunks: 334 },
  { id: "5fce8d66-83df-4fd9-b293-76bb5a4f43c6", name: "Lurline Kub", age: 45, conditions: ["Diabetes", "COPD", "Contact dermatitis"], description: "Chronic disease management with full medication history.", chunks: 321 },
  { id: "2021c4b5-f560-476f-88f2-8524aae95824", name: "Shane Metz", age: 63, conditions: ["Diabetes", "Fibromyalgia", "Lung cancer"], description: "Multi-system conditions with oncology data.", chunks: 310 },
  { id: "887bdea7-43ce-4e17-b614-62b2be1b2c59", name: "Drew Rippin", age: 71, conditions: ["Diabetes", "Hypertension", "Diabetic renal disease"], description: "Diabetic complications with renal involvement.", chunks: 302 },
  { id: "a045ffdb-c70e-47b3-8d4d-041ced44f281", name: "Adelle Daniel", age: 71, conditions: ["Diabetes", "Hypertension", "Stroke"], description: "Cardiovascular events with full encounter history.", chunks: 302 },
  { id: "775775b6-95af-4049-8e23-9bc9a9e82252", name: "Corine Franecki", age: 82, conditions: ["Coronary Heart Disease", "Diabetes", "Osteoarthritis"], description: "Elderly patient with cardiac and joint conditions.", chunks: 288 },
  { id: "89a8e44d-92c2-4539-83b2-755307a2e30f", name: "Erich Larson", age: 78, conditions: ["Diabetes", "Lung cancer", "Asthma"], description: "Respiratory and oncology history with labs.", chunks: 285 },
  { id: "54d5c0ff-89de-4f65-b2a5-c5ecfaf450e8", name: "Liza Marvin", age: 87, conditions: ["Diabetes", "Hypertension", "Stroke", "Gout"], description: "Elderly patient with extensive chronic disease history.", chunks: 282 },
];

export const RECOMMENDED_PROMPTS = [
  "What are the patient's active conditions?",
  "Summarize the patient's medication history.",
  "Does the patient have any known allergies?",
  "What are the patient's recent lab results?",
  "Show me the timeline of clinical events.",
  "When was the patient's last encounter?",
];
