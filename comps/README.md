# PDF Processing API Documentation

A comprehensive guide to using the PDF Processing API for document analysis, compliance extraction, and data export.

## 📋 Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Step-by-Step Guide](#step-by-step-guide)
  - [Step 1: Create Project](#step-1-create-a-new-project)
  - [Step 2: Upload PDF](#step-2-upload-a-pdf-to-the-project)
  - [Step 3: Parse Document](#step-3-run-stage-1-parse-and-create-structure)
  - [Step 4: Extract TOC](#step-4-run-stage-2-extract-toc--compliance-sections)
  - [Step 5: Extract Compliance](#step-5-run-stage-3-extract-compliance-nodestables)
  - [Step 6: Export to Excel](#step-6-run-stage-4-export-to-excel)
  - [Step 7: Export to JSON](#step-7-run-stage-5-export-to-json)
- [Batch Processing](#batch-processing)
- [API Reference](#api-reference)

---

## 🚀 Overview

This API provides a multi-stage pipeline for processing PDF documents, extracting compliance information, and generating structured outputs in Excel and JSON formats.

**Key Features:**
- 📄 PDF parsing and structure analysis
- 📑 Table of Contents (TOC) extraction
- ⚖️ Compliance section identification
- 📊 Excel export with structured data
- 📋 JSON export for programmatic access
- 🔄 Batch processing capabilities

---

## 🏃 Quick Start

### Prerequisites
- API server running on `localhost:8000`
- `curl` and `jq` installed
- PDF file ready for processing


---

## 📖 Step-by-Step Guide

### Step 1: Create a New Project

Create a new project to organize your PDF processing tasks.

```bash
curl -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Demo Project", 
    "description": "Sample for curl test"
  }' | jq
```

**Expected Response:**
```json
{
  "id": "65432abc1234567890abcdef",
  "name": "Demo Project",
  "description": "Sample for curl test",
  "pdfs": []
}
```

> 💾 **Important:** Save the `id` value for subsequent steps

---

### Step 2: Upload a PDF to the Project

Upload your PDF document to the created project.

```bash
curl -X POST "http://localhost:8000/projects/65432abc1234567890abcdef/pdfs" \
  -F "file=@/path/to/your/document.pdf" | jq
```

**Expected Response:**
```json
{
  "id": "abcdefabcdefabcdefabcdef",
  "filename": "document.pdf"
}
```

> 💾 **Important:** Save the PDF `id` value for subsequent steps

---

### Step 3: Run Stage 1 (Parse and Create Structure)

Parse the PDF and create the initial document structure.

```bash
curl -X POST "http://localhost:8000/projects/65432abc1234567890abcdef/pdfs/abcdefabcdefabcdefabcdef/stage/1" | jq
```

**Expected Response:**
```json
{
  "status": "completed",
  "message": "Document parsed successfully",
  "output_directory": "/path/to/output"
}
```

---

### Step 4: Run Stage 2 (Extract TOC & Compliance Sections)

Extract the table of contents and identify potential compliance sections.

```bash
curl -X POST "http://localhost:8000/projects/65432abc1234567890abcdef/pdfs/abcdefabcdefabcdefabcdef/stage/2" | jq
```

**Expected Response:**
```json
{
  "toc": "1. Introduction\n2. Technical Requirements\n2.1 Platform Capabilities\n...",
  "auto_compliance_sections": {
    "technical": "2.1 Platform Capabilities",
    "price": "5.4 Price Schedule"
  }
}
```

> 📝 **Note:** Review the `auto_compliance_sections` and modify if needed for Step 5

---

### Step 5: Run Stage 3 (Extract Compliance Nodes/Tables)

Extract specific compliance sections based on your selections.

#### 5.1: Prepare Compliance Sections

Create a `compliance_sections.json` file with your section selections:

```json
{
  "compliance_sections": {
    "technical": "2.1 Platform Capabilities",
    "price": "5.4 Price Schedule"
  }
}
```

#### 5.2: Execute Extraction

```bash
curl -X POST "http://localhost:8000/projects/65432abc1234567890abcdef/pdfs/abcdefabcdefabcdefabcdef/stage/3" \
  -H "Content-Type: application/json" \
  -d @compliance_sections.json | jq
```

**Expected Response:**
```json
{
  "technical_section": "## 2.1 Platform Capabilities\n\n| Feature | Requirement | Status |\n|---------|-------------|--------|\n| API | REST | ✓ |\n...",
  "price_section": "## 5.4 Price Schedule\n\n| Item | Unit Price | Total |\n|------|------------|-------|\n| License | $1000 | $5000 |\n..."
}
```

> 💾 **Important:** Save this output as `extracted.json` for Step 6

---

### Step 6: Run Stage 4 (Export to Excel)

Generate Excel files from the extracted compliance data.

```bash
curl -X POST "http://localhost:8000/projects/65432abc1234567890abcdef/pdfs/abcdefabcdefabcdefabcdef/stage/4" \
  -H "Content-Type: application/json" \
  -d @extracted.json | jq
```

**Expected Response:**
```json
{
  "excel_files": [
    "/path/to/technical_compliance.xlsx",
    "/path/to/price_compliance.xlsx"
  ],
  "status": "completed"
}
```

---

### Step 7: Run Stage 5 (Export to JSON)

Generate structured JSON outputs for programmatic access.

```bash
curl -X POST "http://localhost:8000/projects/65432abc1234567890abcdef/pdfs/abcdefabcdefabcdefabcdef/stage/5" | jq
```

**Expected Response:**
```json
{
  "json_files": [
    "/path/to/technical_data.json",
    "/path/to/price_data.json",
    "/path/to/combined_output.json"
  ],
  "status": "completed"
}
```

---

## 🔄 Batch Processing (Beta version - not recommended)

### Run All Stages at Once

For convenience, you can execute all stages in a single command:

```bash
curl -X POST "http://localhost:8000/projects/65432abc1234567890abcdef/pdfs/abcdefabcdefabcdefabcdef/run_all" | jq
```

**Expected Response:**
```json
{
  "status": "completed",
  "auto_compliance_sections": {
    "technical": "2.1 Platform Capabilities",
    "price": "5.4 Price Schedule"
  },
  "excel_files": [
    "/path/to/technical_compliance.xlsx",
    "/path/to/price_compliance.xlsx"
  ],
  "json_files": [
    "/path/to/combined_output.json"
  ],
  "processing_time": "45.2 seconds"
}
```

---

## 📚 API Reference

### Base URL
```
http://localhost:8000
```

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/projects` | Create a new project |
| `POST` | `/projects/{project_id}/pdfs` | Upload PDF to project |
| `POST` | `/projects/{project_id}/pdfs/{pdf_id}/stage/1` | Parse document structure |
| `POST` | `/projects/{project_id}/pdfs/{pdf_id}/stage/2` | Extract TOC and compliance sections |
| `POST` | `/projects/{project_id}/pdfs/{pdf_id}/stage/3` | Extract compliance data |
| `POST` | `/projects/{project_id}/pdfs/{pdf_id}/stage/4` | Export to Excel |
| `POST` | `/projects/{project_id}/pdfs/{pdf_id}/stage/5` | Export to JSON |
| `POST` | `/projects/{project_id}/pdfs/{pdf_id}/run_all` | Execute all stages |

### Response Codes

| Code | Description |
|------|-------------|
| `200` | Success |
| `400` | Bad Request |
| `404` | Resource Not Found |
| `500` | Internal Server Error |

---

## 💡 Tips & Best Practices

- **Save IDs**: Always save project and PDF IDs for subsequent API calls
- **Review Compliance Sections**: Check auto-detected compliance sections before Stage 3
- **Use Batch Processing**: Use `run_all` for simpler workflows
- **Error Handling**: Check response status codes and messages
- **File Paths**: Ensure PDF file paths are accessible to the API server

---

## 🆘 Troubleshooting

**Common Issues:**

1. **File Not Found**: Ensure PDF path is correct and accessible
2. **Invalid JSON**: Validate JSON syntax in request bodies
3. **Missing Dependencies**: Ensure `jq` is installed for formatted output
4. **Server Connection**: Verify API server is running on `localhost:8000`

---

*For additional support or feature requests, please contact the development team.*