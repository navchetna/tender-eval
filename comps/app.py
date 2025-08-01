import os
import re
import json
import shutil
from typing import List, Dict, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId
import uvicorn
import pandas as pd
import io

from dotenv import load_dotenv
import motor.motor_asyncio

from comps.parsers.tree import Tree
from comps.parsers.text import Text
from comps.parsers.table import Table
from comps.parsers.treeparser import TreeParser
from comps.dataprep.excel_to_json_price import excel_to_price_compliance_json
from comps.dataprep.excel_to_json_tech import excel_to_technical_compliance_json

# ------------ CONFIG & INIT -----------------
load_dotenv()
MONGO_URI = 'mongodb://localhost:27100'
DB_NAME = os.environ.get('DB_NAME', 'tender_eval')
OUTPUT_DIR = 'tender-eval-outputs'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --------- FastAPI and CORS (for local dev) -----------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

# --------- Mongo connection ------------
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = mongo_client[DB_NAME]
projects_coll = db['projects']
pdfs_coll = db['pdfs']

# -------- Helper Models ----------------
class ProjectCreateReq(BaseModel):
    name: str
    description: Optional[str] = None

class ProjectOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    pdfs: List[str] = []

class PDFMetadataOut(BaseModel):
    id: str
    filename: str

# ---------- Utility Functions ---------------

def parse_pdf_pipeline_stages():
    # Just a names/ids list for the frontend
    return [
        {"id": 1, "name": "Parse and create structure"},
        {"id": 2, "name": "Extract TOC & Compliance Sections"},
        {"id": 3, "name": "Extract Compliance Nodes/Tables"},
        {"id": 4, "name": "Export to Excel"},
        {"id": 5, "name": "Export to JSON"},
    ]

def pdf_output_dir(project_id, pdf_id):
    return os.path.join(OUTPUT_DIR, project_id, pdf_id)

async def save_pdf_in_db(project_id, filename, bytes_data):
    doc = {
        "project_id": project_id,
        "filename": filename,
        "data": bytes_data,
    }
    result = await pdfs_coll.insert_one(doc)
    return str(result.inserted_id)

async def get_pdf_bytes(pdf_id):
    pdf = await pdfs_coll.find_one({'_id': ObjectId(pdf_id)})
    if not pdf:
        raise HTTPException(404, 'PDF not found')
    return pdf["filename"], pdf["data"]

async def get_pdf_meta_for_project(project_id):
    pdfs = pdfs_coll.find({'project_id': project_id})
    result = []
    async for pdf in pdfs:
        result.append({
            "id": str(pdf["_id"]),
            "filename": pdf["filename"]
        })
    return result

def save_bytes_to_disk(path, bytes_data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(bytes_data)

def fuzzy_matches(heading, query):
    from fuzzywuzzy import fuzz
    score = fuzz.ratio(heading.strip().lower(), query.strip().lower())
    return score >= 90

def find_node_by_level_or_title(rootNode, query):
    if fuzzy_matches(rootNode.get_heading(), query):
        return rootNode
    for i in range(rootNode.get_length_children()):
        result = find_node_by_level_or_title(rootNode.get_child(i), query)
        if result:
            return result
    return None

def retrieve_from_pdf(target_node):
    if target_node:
        for item in target_node.get_content():
            if hasattr(item, "markdown_content"):
                return item.markdown_content
    return None

def markdown_to_df(markdown_content, section_title):
    section_title = section_title.replace(" ", "_")
    lines = [line for line in markdown_content.splitlines() if line.strip().startswith('|')]
    cleaned_table_str = '\n'.join(lines)
    df = pd.read_csv(io.StringIO(cleaned_table_str), sep='|', engine='python', skipinitialspace=True)
    df = df.iloc[1:]
    df = df.drop(df.columns[[0, -1]], axis=1)
    df.columns = [col.strip() for col in df.columns]
    return df

def combine_price_and_tech_json(json_dir_path, output_filename="combined.json"):
    combined_data = {
        "price_compliance": {},
        "technical_compliance": {}
    }
    for file_name in os.listdir(json_dir_path):
        if not file_name.endswith('.json'):
            continue
        file_path = os.path.join(json_dir_path, file_name)
        lower_name = file_name.lower()
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if "price" in lower_name:
            combined_data['price_compliance'] = data
        elif "tech" in lower_name:
            combined_data['technical_compliance'] = data
    output_path = os.path.join(json_dir_path, output_filename)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(combined_data, f, indent=4)
    return output_path

# --------------- Stage Functions (as previously modularized, but sync for backend CLI) ---------------

def stage_parse_pdf(pdf_bytes_path, output_path):
    tree = Tree(pdf_bytes_path)
    parser = TreeParser()
    parser.populate_tree(tree)
    parser.generate_output_text(tree)
    parser.generate_output_json(tree)
    return tree

def stage_extract_toc(tree, pdf_output_dir):
    toc_path = os.path.join(pdf_output_dir, 'toc.txt')
    with open(toc_path, 'r', encoding='utf-8') as f:
        toc_content = f.read()
    return toc_content

def stage_select_compliance_sections(toc_content, ask_groq_function):
    sections_str = ask_groq_function(toc_content)
    compliance_sections = json.loads(sections_str)
    return compliance_sections

def stage_extract_section_nodes(tree, compliance_sections):
    extracted = {}
    for sec_type, sec_title in compliance_sections.items():
        node = find_node_by_level_or_title(tree.rootNode, sec_title)
        markdown = retrieve_from_pdf(node)
        extracted[sec_type] = {
            "section_title": sec_title,
            "markdown": markdown
        }
    return extracted

def stage_convert_to_df(extracted):
    dfs = {}
    for k, v in extracted.items():
        if v["markdown"]:
            df = markdown_to_df(v["markdown"], v["section_title"])
            dfs[k] = df
    return dfs

def stage_save_excel_files(pdf_output_dir, dfs):
    excel_dir = os.path.join(pdf_output_dir, 'excel')
    os.makedirs(excel_dir, exist_ok=True)
    excel_paths = {}
    for k, df in dfs.items():
        excel_path = os.path.join(excel_dir, f"{k}.xlsx")
        df.to_excel(excel_path, index=False)
        excel_paths[k] = excel_path
    return excel_paths

def stage_transform_to_json(pdf_output_dir, excel_paths):
    json_dir = os.path.join(pdf_output_dir, 'json')
    os.makedirs(json_dir, exist_ok=True)
    json_outputs = {}
    for k, path in excel_paths.items():
        if "price" in k:
            compliance_json = excel_to_price_compliance_json(path)
        else:
            compliance_json = excel_to_technical_compliance_json(path)
        json_path = os.path.join(json_dir, f"{k}.json")
        with open(json_path, 'w') as fh:
            json.dump(compliance_json, fh, indent=4)
        json_outputs[k] = json_path
    combined_path = combine_price_and_tech_json(json_dir)
    return json_outputs

# --------------- Ask Groq: Proxy function. You can keep your existing -----------------
def ask_groq_with_file_content(toc_content):
    # Use your existing LLM call as before, e.g., with groq sdk
    # Supports both file_path or direct toc_content strings
    # Return just the LLM JSON result as a string
    from groq import Groq
    client = Groq(api_key="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")
    system_prompt = """
        You are an information extraction API that identifies the most relevant sections from a tender document's Table of Contents (TOC) for technical and price compliance.
        
        Your task is to identify exactly two entries:
        1) One section that is the most relevant for evaluating technical compliance.
        2) One section that is the most relevant for evaluating price/commercial compliance.
        
        - The "technical" field should contain the single TOC entry that is most relevant to **technical compliance**, such as Platform Capabilities, functional requirements, platform specifications, implementation details, architecture.

        - The "price" field should contain the single most relevant entry for **price compliance**, which typically refers to a **price bid table** or **price evaluation section**. These are usually structured tables in the document where bidders must approximate the cost of delivering each line item. These entries are often titled **"Price Bid Evaluation"**, **"Commercial Bid Evaluation"**, or similar.
        
        You must respond only with JSON in the following format:

        {
            "technical": "<section_number> <section_title>",
            "price": "<section_number> <section_title>"
        }

        These sections will be used to compare the tender requirements against bidder documents, so it is critical to select the sections that provide the clearest and most complete technical and price requirement details respectively. Even a single extra whitespace can cause the prohram to fail to find the section, so ensure the output is exactly as specified. You should EXACTLY match the section titles as they appear in the TOC, including any leading numbers or formatting.
    
        Respond only with the JSON object described above. Do not include any explanation, preamble, or notes.
    """
    chat_completion = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {
               
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": toc_content
                }
        ],
        response_format={"type": "json_object"}
    )
    return chat_completion.choices[0].message.content

# --------------- ROUTES -------------------

@app.get("/projects", response_model=List[ProjectOut])
async def list_projects():
    cursor = projects_coll.find()
    res = []
    async for proj in cursor:
        pdfs = await get_pdf_meta_for_project(str(proj["_id"]))
        res.append(ProjectOut(
            id=str(proj["_id"]),
            name=proj["name"],
            description=proj.get("description"),
            pdfs=[pdf['id'] for pdf in pdfs]
        ))
    return res

@app.post("/projects", response_model=ProjectOut)
async def create_project(req: ProjectCreateReq):
    doc = {
        "name": req.name,
        "description": req.description or ""
    }
    result = await projects_coll.insert_one(doc)
    return ProjectOut(id=str(result.inserted_id), name=req.name, description=req.description, pdfs=[])

@app.post("/projects/{project_id}/pdfs", response_model=PDFMetadataOut)
async def upload_pdf(project_id: str, file: UploadFile = File(...)):
    bytes_data = await file.read()
    pdf_id = await save_pdf_in_db(project_id, file.filename, bytes_data)
    return PDFMetadataOut(id=pdf_id, filename=file.filename)

@app.get("/projects/{project_id}/pdfs", response_model=List[PDFMetadataOut])
async def list_project_pdfs(project_id: str):
    pdfs = await get_pdf_meta_for_project(project_id)
    return [PDFMetadataOut(id=pdf['id'], filename=pdf['filename']) for pdf in pdfs]

@app.get("/projects/{project_id}/pdfs/{pdf_id}/download")
async def download_pdf(project_id: str, pdf_id: str):
    filename, pdf_bytes = await get_pdf_bytes(pdf_id)
    temp_path = f"/tmp/{pdf_id}-{filename}"
    save_bytes_to_disk(temp_path, pdf_bytes)
    return FileResponse(temp_path, media_type='application/pdf', filename=filename)

@app.get("/pipeline/stages")
async def get_pipeline_stages():
    return parse_pdf_pipeline_stages()

# ------------------- PIPELINE STAGE ENDPOINTS, all async calls and temp-files ----------------------

@app.post("/projects/{project_id}/pdfs/{pdf_id}/stage/{stage_id}")
async def run_pipeline_stage(project_id: str, pdf_id: str, stage_id: int, request: Request):
    # Load the latest available state, operate on it, and return output
    # For large data like markdown tables, you may want to trim or send links for download

    # 0: fetch PDF from Mongo to disk so parser can handle it
    filename, pdf_bytes = await get_pdf_bytes(pdf_id)
    output_dir = pdf_output_dir(project_id, pdf_id)
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, filename)
    save_bytes_to_disk(pdf_path, pdf_bytes)

    # Stage 1: Parse and create structure
    if stage_id == 1:
        tree = stage_parse_pdf(pdf_path, output_dir)
        return {"status": "parsed", "output_dir": output_dir}

    # Stage 2: Extract TOC and get Compliance Section Candidates via LLM
    elif stage_id == 2:
        tree = Tree(pdf_path)
        toc_content = stage_extract_toc(tree, output_dir)
        # Offer the raw toc_content for UI to display & correct, also provide auto-suggested by LLM
        auto_suggested = stage_select_compliance_sections(toc_content, ask_groq_with_file_content)
        return {"toc": toc_content, "auto_compliance_sections": auto_suggested}

    # Stage 3: (UI can pass `compliance_sections` for manual override, else run using suggested)
    elif stage_id == 3:
        data = await request.json()
        compliance_sections = data.get("compliance_sections")
        if not compliance_sections:
            raise HTTPException(400, "Missing compliance_sections")
        tree = Tree(pdf_path)
        extracted = stage_extract_section_nodes(tree, compliance_sections)
        # return raw markdown/tables for UI display
        return extracted

    # Stage 4: Export extracted sections to DataFrames and save Excel files
    elif stage_id == 4:
        data = await request.json()
        extracted = data.get("extracted")
        dfs = {}
        # For each k: {section_title, markdown}
        for k, v in extracted.items():
            if v["markdown"]:
                df = markdown_to_df(v["markdown"], v["section_title"])
                dfs[k] = df
        excel_paths = stage_save_excel_files(output_dir, dfs)
        return {"excel_paths": excel_paths}

    # Stage 5: Transform compliance excels to json
    elif stage_id == 5:
        excel_dir = os.path.join(output_dir, 'excel')
        excel_paths = {f.split(".")[0]: os.path.join(excel_dir, f) for f in os.listdir(excel_dir) if f.endswith(".xlsx")}
        json_outputs = stage_transform_to_json(output_dir, excel_paths)
        return {"json_outputs": json_outputs, "output_dir": output_dir}

    else:
        raise HTTPException(400, f"Unknown pipeline stage: {stage_id}")

# ----------- RUN-ALL PIPELINE ENDPOINT FOR TESTING/BATCH RUNNING (Backend) --------

@app.post("/projects/{project_id}/pdfs/{pdf_id}/run_all")
async def run_all_stages_one_pdf(project_id: str, pdf_id: str):
    filename, pdf_bytes = await get_pdf_bytes(pdf_id)
    output_dir = pdf_output_dir(project_id, pdf_id)
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, filename)
    save_bytes_to_disk(pdf_path, pdf_bytes)

    tree = stage_parse_pdf(pdf_path, output_dir)
    toc_content = stage_extract_toc(tree, output_dir)
    auto_sections = stage_select_compliance_sections(toc_content, ask_groq_with_file_content)
    extracted = stage_extract_section_nodes(tree, auto_sections)
    dfs = stage_convert_to_df(extracted)
    excel_paths = stage_save_excel_files(output_dir, dfs)
    json_outputs = stage_transform_to_json(output_dir, excel_paths)
    return {"success": True, "auto_sections": auto_sections, "json_paths": json_outputs, "output_dir": output_dir}

# ----------- SCRIPT RUNNER FOR LOCAL BATCH TESTING OF WHOLE PIPELINE ---------------

def run_local_pipeline_for_project(project_id):
    import asyncio
    loop = asyncio.get_event_loop()
    pdfs = loop.run_until_complete(get_pdf_meta_for_project(project_id))
    for pdf in pdfs:
        print(f"Processing {pdf['filename']}...")
        result = loop.run_until_complete(run_all_stages_one_pdf(project_id, pdf['id']))
        print(result)
    print("All PDFs processed!")

# ----------- MAIN -----------------

if __name__ == "__main__":
    import sys
    # To run API:  python main.py api
    # To run local processing:  python main.py process <project_id>
    if len(sys.argv) > 1 and sys.argv[1] == "api":
        uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
    elif len(sys.argv) > 2 and sys.argv[1] == "process":
        run_local_pipeline_for_project(sys.argv[2])
    else:
        print("Usage: python main.py api OR python main.py process <project_id>")
