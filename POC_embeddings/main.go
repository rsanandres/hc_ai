// main.go
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
)

type Bundle struct {
	Type         string  `json:"type"`
	Entry        []Entry `json:"entry"`
	ResourceType string  `json:"resourceType"`
}

type Entry struct {
	FullURL  string                 `json:"fullUrl"`
	Resource map[string]interface{} `json:"resource"`
}

func main() {
	// Process all JSON files in a folder
	dataDir := "../data/fhir"

	fmt.Printf("Processing all JSON files in: %s\n", dataDir)

	// Get all JSON files
	files, err := filepath.Glob(filepath.Join(dataDir, "*.json"))
	if err != nil {
		log.Fatalf("Error reading directory: %v", err)
	}

	if len(files) == 0 {
		log.Printf("No JSON files found in %s", dataDir)
		return
	}

	fmt.Printf("Found %d JSON files\n\n", len(files))

	// Process each file
	for i, filePath := range files {
		fmt.Printf("[%d/%d] Processing: %s\n", i+1, len(files), filepath.Base(filePath))
		processFile(filePath)
		fmt.Println() // Empty line between files
	}

	fmt.Printf("\n✓ Completed processing %d files\n", len(files))
}

func processFile(filePath string) {
	data, err := os.ReadFile(filePath)
	if err != nil {
		log.Printf("Error reading file %s: %v", filePath, err)
		return
	}

	var bundle Bundle
	if err := json.Unmarshal(data, &bundle); err != nil {
		log.Printf("Error parsing JSON in %s: %v", filePath, err)
		return
	}

	if bundle.ResourceType != "Bundle" {
		log.Printf("Warning: %s is not a Bundle resource", filePath)
		return
	}

	fmt.Printf("  Found %d entries\n", len(bundle.Entry))

	// First, find the Patient resource to get patient ID
	patientID := extractPatientID(bundle.Entry)

	for i, entry := range bundle.Entry {
		resourceType, ok := entry.Resource["resourceType"].(string)
		if !ok {
			log.Printf("  Entry %d: Missing resourceType", i)
			continue
		}

		id, _ := entry.Resource["id"].(string)
		if id == "" {
			// Some resources might not have an id, use fullUrl as fallback
			id = entry.FullURL
		}

		// Extract meaningful content from the resource
		content := extractContent(entry.Resource, resourceType)

		// Skip if content is empty
		if content == "" {
			log.Printf("  Entry %d (%s): Skipping - no extractable content", i, resourceType)
			continue
		}

		// Serialize the original resource JSON
		resourceJSONBytes, err := json.Marshal(entry.Resource)
		resourceJSON := ""
		if err == nil {
			resourceJSON = string(resourceJSONBytes)
		} else {
			log.Printf("  Entry %d (%s): Warning - could not serialize resource JSON: %v", i, resourceType, err)
		}

		flatData := map[string]string{
			"id":           id,
			"fullUrl":      entry.FullURL,
			"resourceType": resourceType,
			"content":      content,
			"patientId":    patientID,    // Add patient ID to all resources
			"resourceJson": resourceJSON, // Add original JSON for RecursiveJsonSplitter
			"sourceFile":   filePath,     // Add source file path
		}

		sendToPipeline(flatData)
	}
}

func extractPatientID(entries []Entry) string {
	// Find the Patient resource and extract its ID
	for _, entry := range entries {
		if resourceType, ok := entry.Resource["resourceType"].(string); ok && resourceType == "Patient" {
			if id, ok := entry.Resource["id"].(string); ok && id != "" {
				return id
			}
			// Fallback to fullUrl if no id
			return entry.FullURL
		}
	}
	return "unknown"
}

func extractContent(resource map[string]interface{}, resourceType string) string {
	var parts []string

	// Try to get text.div first (if available)
	if text, ok := resource["text"].(map[string]interface{}); ok {
		if div, ok := text["div"].(string); ok && div != "" {
			// Clean HTML tags for better text extraction
			div = cleanHTML(div)
			if div != "" {
				return div
			}
		}
	}

	// Build content based on resource type
	switch resourceType {
	case "Patient":
		parts = append(parts, "Patient Information:")
		if name, ok := resource["name"].([]interface{}); ok && len(name) > 0 {
			if nameObj, ok := name[0].(map[string]interface{}); ok {
				if family, ok := nameObj["family"].(string); ok {
					parts = append(parts, fmt.Sprintf("Name: %s", family))
				}
				if given, ok := nameObj["given"].([]interface{}); ok && len(given) > 0 {
					if givenStr, ok := given[0].(string); ok {
						parts = append(parts, fmt.Sprintf("%s", givenStr))
					}
				}
			}
		}
		if gender, ok := resource["gender"].(string); ok {
			parts = append(parts, fmt.Sprintf("Gender: %s", gender))
		}
		if birthDate, ok := resource["birthDate"].(string); ok {
			parts = append(parts, fmt.Sprintf("Date of Birth: %s", birthDate))
		}

	case "Condition":
		parts = append(parts, "Medical Condition:")
		if code, ok := resource["code"].(map[string]interface{}); ok {
			if text, ok := code["text"].(string); ok {
				parts = append(parts, text)
			} else if coding, ok := code["coding"].([]interface{}); ok && len(coding) > 0 {
				if codingObj, ok := coding[0].(map[string]interface{}); ok {
					if display, ok := codingObj["display"].(string); ok {
						parts = append(parts, display)
					}
				}
			}
		}
		if status, ok := resource["clinicalStatus"].(string); ok {
			parts = append(parts, fmt.Sprintf("Status: %s", status))
		}
		if onset, ok := resource["onsetDateTime"].(string); ok {
			parts = append(parts, fmt.Sprintf("Onset: %s", onset))
		}

	case "Observation":
		parts = append(parts, "Clinical Observation:")
		if code, ok := resource["code"].(map[string]interface{}); ok {
			if text, ok := code["text"].(string); ok {
				parts = append(parts, text)
			} else if coding, ok := code["coding"].([]interface{}); ok && len(coding) > 0 {
				if codingObj, ok := coding[0].(map[string]interface{}); ok {
					if display, ok := codingObj["display"].(string); ok {
						parts = append(parts, display)
					}
				}
			}
		}
		if valueQty, ok := resource["valueQuantity"].(map[string]interface{}); ok {
			if value, ok := valueQty["value"].(float64); ok {
				if unit, ok := valueQty["unit"].(string); ok {
					parts = append(parts, fmt.Sprintf("Value: %.2f %s", value, unit))
				} else {
					parts = append(parts, fmt.Sprintf("Value: %.2f", value))
				}
			}
		}
		if effective, ok := resource["effectiveDateTime"].(string); ok {
			parts = append(parts, fmt.Sprintf("Date: %s", effective))
		}

	case "Encounter":
		parts = append(parts, "Healthcare Encounter:")
		if encType, ok := resource["type"].([]interface{}); ok && len(encType) > 0 {
			if typeObj, ok := encType[0].(map[string]interface{}); ok {
				if text, ok := typeObj["text"].(string); ok {
					parts = append(parts, text)
				} else if coding, ok := typeObj["coding"].([]interface{}); ok && len(coding) > 0 {
					if codingObj, ok := coding[0].(map[string]interface{}); ok {
						if display, ok := codingObj["display"].(string); ok {
							parts = append(parts, display)
						}
					}
				}
			}
		}
		if period, ok := resource["period"].(map[string]interface{}); ok {
			if start, ok := period["start"].(string); ok {
				parts = append(parts, fmt.Sprintf("Start: %s", start))
			}
		}
		if reason, ok := resource["reason"].(map[string]interface{}); ok {
			if coding, ok := reason["coding"].([]interface{}); ok && len(coding) > 0 {
				if codingObj, ok := coding[0].(map[string]interface{}); ok {
					if display, ok := codingObj["display"].(string); ok {
						parts = append(parts, fmt.Sprintf("Reason: %s", display))
					}
				}
			}
		}

	case "MedicationRequest":
		parts = append(parts, "Medication Prescription:")
		if medRef, ok := resource["medicationReference"].(map[string]interface{}); ok {
			if ref, ok := medRef["reference"].(string); ok {
				parts = append(parts, fmt.Sprintf("Medication Reference: %s", ref))
			}
		}
		if status, ok := resource["status"].(string); ok {
			parts = append(parts, fmt.Sprintf("Status: %s", status))
		}
		if authored, ok := resource["authoredOn"].(string); ok {
			parts = append(parts, fmt.Sprintf("Prescribed: %s", authored))
		}

	case "Medication":
		parts = append(parts, "Medication:")
		if code, ok := resource["code"].(map[string]interface{}); ok {
			if text, ok := code["text"].(string); ok {
				parts = append(parts, text)
			} else if coding, ok := code["coding"].([]interface{}); ok && len(coding) > 0 {
				if codingObj, ok := coding[0].(map[string]interface{}); ok {
					if display, ok := codingObj["display"].(string); ok {
						parts = append(parts, display)
					}
				}
			}
		}

	case "Immunization":
		parts = append(parts, "Immunization:")
		if vaccineCode, ok := resource["vaccineCode"].(map[string]interface{}); ok {
			if coding, ok := vaccineCode["coding"].([]interface{}); ok && len(coding) > 0 {
				if codingObj, ok := coding[0].(map[string]interface{}); ok {
					if display, ok := codingObj["display"].(string); ok {
						parts = append(parts, display)
					}
				}
			}
		}
		if date, ok := resource["date"].(string); ok {
			parts = append(parts, fmt.Sprintf("Date: %s", date))
		}

	case "DiagnosticReport":
		parts = append(parts, "Diagnostic Report:")
		if code, ok := resource["code"].(map[string]interface{}); ok {
			if coding, ok := code["coding"].([]interface{}); ok && len(coding) > 0 {
				if codingObj, ok := coding[0].(map[string]interface{}); ok {
					if display, ok := codingObj["display"].(string); ok {
						parts = append(parts, display)
					}
				}
			}
		}
		if effective, ok := resource["effectiveDateTime"].(string); ok {
			parts = append(parts, fmt.Sprintf("Date: %s", effective))
		}

	case "Procedure":
		parts = append(parts, "Medical Procedure:")
		if code, ok := resource["code"].(map[string]interface{}); ok {
			if coding, ok := code["coding"].([]interface{}); ok && len(coding) > 0 {
				if codingObj, ok := coding[0].(map[string]interface{}); ok {
					if display, ok := codingObj["display"].(string); ok {
						parts = append(parts, display)
					}
				}
			}
		}
		if performed, ok := resource["performedDateTime"].(string); ok {
			parts = append(parts, fmt.Sprintf("Performed: %s", performed))
		}

	case "Organization":
		parts = append(parts, "Organization:")
		if name, ok := resource["name"].(string); ok {
			parts = append(parts, name)
		}

	default:
		// For unknown resource types, try to extract code/text fields
		if code, ok := resource["code"].(map[string]interface{}); ok {
			if text, ok := code["text"].(string); ok {
				parts = append(parts, text)
			} else if coding, ok := code["coding"].([]interface{}); ok && len(coding) > 0 {
				if codingObj, ok := coding[0].(map[string]interface{}); ok {
					if display, ok := codingObj["display"].(string); ok {
						parts = append(parts, display)
					}
				}
			}
		}
	}

	if len(parts) == 0 {
		return ""
	}

	return strings.Join(parts, " ")
}

func cleanHTML(html string) string {
	// Simple HTML tag removal
	html = strings.ReplaceAll(html, "<div>", "")
	html = strings.ReplaceAll(html, "</div>", "")
	html = strings.ReplaceAll(html, "<a", "")
	html = strings.ReplaceAll(html, "</a>", "")
	html = strings.ReplaceAll(html, ">", " ")
	html = strings.ReplaceAll(html, "<", "")
	html = strings.TrimSpace(html)
	return html
}

func sendToPipeline(data map[string]string) {
	jsonData, err := json.Marshal(data)
	if err != nil {
		log.Printf("Error marshaling data: %v", err)
		return
	}

	resp, err := http.Post("http://localhost:8000/ingest", "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		log.Printf("Error sending to pipeline: %v", err)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		log.Printf("Pipeline returned status %d for ID: %s", resp.StatusCode, data["id"])
		return
	}

	fmt.Printf("  ✓ Ingested: %s (%s)\n", data["id"], data["resourceType"])
}
