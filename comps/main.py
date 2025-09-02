import re
import os
import sys
import json
import numpy as np
import pandas as pd
from groq import Groq
from io import StringIO
from dotenv import load_dotenv

from comps.parsers.tree import Tree
from comps.parsers.text import Text
from comps.parsers.table import Table
from comps.parsers.treeparser import TreeParser
from comps.dataprep.excel_to_json_price import excel_to_price_compliance_json
from comps.dataprep.excel_to_json_tech import excel_to_technical_compliance_json

load_dotenv()
# main.py calls pdfparse.tree
# the pdfparse script should loop through all pdfs and and return the tree for each
# the returned tree should then be sent to the rest of the pipeline 

PDF_DIR = os.environ.get("PDF_DIR")
print("Parsing pdfs in: ", PDF_DIR)

GROQ_API_KEY= os.getenv('GROQ_API_KEY')
OUTPUT_DIR = 'out/'

# instead of a single path, this should take a directory and loop through files


def parse_pdf(pdf_path):
    file_dir_name = pdf_path.split('/')[-1].replace('.pdf','')
    # Create the Tree and parser
    tree = Tree(pdf_path)
    parser = TreeParser(f"out/{file_dir_name}")
    # Populate the tree
    parser.populate_tree(tree)
    # Save hierarchy as text
    parser.generate_output_text(tree)
    # Save hierarchy as JSON
    parser.generate_output_json(tree)

    print("Parsing complete!")
    print(f"See outputs in: out/{tree.file.split('/')[-1].replace('.pdf','')}")
    return tree

def read_file_content(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        return content
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None
    except Exception as e:
        print(f"Error reading file: {e}")
        return None

def ask_groq_with_file_content(file_path):
    client = Groq(api_key=GROQ_API_KEY)

    document_content = read_file_content(file_path)
    if document_content is None:
        return []

    toc_content = f"TOC Content:\n```\n{document_content}\n```\n"

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
    
    try:
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

        response = chat_completion.choices[0].message.content
        return response

    except Exception as e:
        print(f"An error occurred: {e}")
        return()

def fuzzy_matches(heading, query):
    from fuzzywuzzy import fuzz

    score = fuzz.ratio(heading.strip().lower(), query.strip().lower())
    return score >= 90

def find_node_by_level_or_title(rootNode, query):
    print("Searching for:", query)
    
    if fuzzy_matches(rootNode.get_heading(), query):
        print(f"High score for '{rootNode.get_heading().strip()}' with '{query.strip()}'!\n")
        return rootNode

    for i in range(rootNode.get_length_children()):
        result = find_node_by_level_or_title(rootNode.get_child(i), query)
        if result:
            return result

    return None

def retrieve_from_pdf(target_node):
    if target_node:
        print("Found Node:", target_node.get_heading())
        # print("Contents:")
        for item in target_node.get_content():
            if hasattr(item, "markdown_content"):
                # print("TABLE:")
                # print(item.markdown_content)
                return(item.markdown_content)
    else:
        print(" No table/ Node found not found")
        
    return(None)

def markdown_to_df(markdown_content, section_title):
    section_title = section_title.replace(" ", "_")
    # clean_table = re.sub(r'<br>', ' ', markdown_content)

    lines = [line for line in markdown_content.splitlines() if line.strip().startswith('|')]
    cleaned_table_str = '\n'.join(lines)

    df = pd.read_csv(StringIO(cleaned_table_str), sep='|', engine='python', skipinitialspace=True)

    df = df.iloc[1:]
    df = df.drop(df.columns[[0, -1]], axis=1)
    df.columns = [col.strip() for col in df.columns]
    #print (df)
    print("DataFrame created from markdown content")

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
    
    print(f"Combined JSON saved to {output_path}")

# tree = parse_pdf(PDF_PATH)
def ingest_pdf_directory(pdf_dir):
    # loop through a directory which has the documents
    # functions used:
    # parse_pdf(pdf_path) - parses a single pdf and returns a tree object
    # read_file_content(file_path) - reads the content of a file
    for filename in os.listdir(pdf_dir):
        if filename.endswith('.pdf'):
            ## PART 1 create a tree in memory for each pdf -> this also creates their .md and toc.txt
            pdf_path = os.path.join(pdf_dir, filename)
            print(f"\nParsing file: {pdf_path}")
            tree = parse_pdf(pdf_path)
            print(f"Done parsing {filename}!")

            print("Extracting TOC from outputs")
            toc_path = f"out/{os.path.splitext(filename)[0]}/toc.txt"
            print(f"Found TOC at: {toc_path}")

            ## PART 2 - Use the toc.txt to generate tech and price requirements using Groq
            sections_str = ask_groq_with_file_content(toc_path)
            compliance_sections = json.loads(sections_str)

            ## Part 3 - Now we have a dictionary of requirements, both tech and price
            ## we need to find the nodes in the TREE that match these requirements
            ## once we find these, we extract those parts from the markdown and convert them into panda dataframes (if theyre tables)
            file_dir_name = filename.replace('.pdf','')
            json_dir = os.path.join(OUTPUT_DIR, file_dir_name, 'json')
            excel_dir = os.path.join(OUTPUT_DIR, file_dir_name, 'excel')
            os.makedirs(json_dir, exist_ok=True)
            os.makedirs(excel_dir, exist_ok=True)

            for section_number, section_title in compliance_sections.items():
                section_title = section_title[2:] if section_title else None

                target_node = find_node_by_level_or_title(tree.rootNode, section_title)
                markdown_content = retrieve_from_pdf(target_node)

                df = markdown_to_df(markdown_content, section_title)
                section_title = section_title.replace(' ', '_')

                excel_path = os.path.join(excel_dir, f"{section_title}.xlsx")
                df.to_excel(excel_path, index=False)
                print(f"DataFrame saved to '{excel_path}'")
                # PART 4 - Now we have the df for both technical & price compliance for a particular pdf -> converted into excel sheets
                # => 2 excel sheets for each pdf
                # convert these excel sheets into json files

                json_path = os.path.join(json_dir, f"{section_title}.json")
                compliance_json = ""
                if "price" in excel_path.lower():
                    compliance_json = excel_to_price_compliance_json(excel_path)
                else:
                    compliance_json = excel_to_technical_compliance_json(excel_path)
                with open(json_path, 'w') as fh:
                        json.dump(compliance_json, fh, indent=4)
                
                print(f"Saving the JSON output for {filename}...")
                combine_price_and_tech_json(json_dir)
                print("Saved JSON output!")
                # PART 5 - TO DO (but present at the bottom of the script(commented): 
                # call the evaluate_responses function that would ideally take multiple json strings
                # and evaluate the responses based on the scores



if __name__ == "__main__":
    all_trees = ingest_pdf_directory(PDF_DIR)
    # sys.exit(1)
 



# To integrate --------------------------------------------------------------------------------------------------------
# import json
# import os
# from groq import Groq

# # Set your Groq API Key here
# GROQ_API_KEY = ""

# # Paths to JSON files
# TENDER_FILE = "/home/aayush/tender-eval/comps/dataprep/json-outputs/tender-requirements.json"
# #Dynamically taking in the Bids!
# directory="/home/aayush/tender-eval/comps/dataprep/json-outputs"
# lst=os.listdir(directory)
# bid_no=int(len(lst)/3)
# #bid_no = int(3)
# BIDDER_FILES = []

# for j in range(bid_no):
#     k = j + 1
#     BIDDER_FILES.append(f"/home/aayush/tender-eval/comps/dataprep/json-outputs/bidder-response-{k}.json")


# client = Groq(api_key=GROQ_API_KEY)

# def load_json(file_path):
#     with open(file_path, "r") as f:
#         return json.load(f)

# def format_json_as_text(json_obj):
#     return json.dumps(json_obj, indent=2)

# def construct_prompt(tender_str, bidder_str):
#     st=str("")
#     for j in range(bid_no):
#             st+=("BIDDER RESPONSE JSON "+str(j+1)+"\n")
#             st+=(bidder_str[j]) 
#     prompt = f"""
#         You will be provided:
#         1. The Tender Requirements JSON structure — this defines all expected fields and compliance criteria. These fields may be present but contain empty or placeholder values.
#         2. Multiple Bidder Response JSON documents, each in the same format as the tender, but filled in with actual bids from different vendors.

#         Your tasks:
#         - Please Evaluate each bidder's JSON response against the tender requirements.
#         - Please Determine how well each bidder meets the requirements.
#         - Please Score each bidder out of 100 based on:
#         - Technical compliance
#         - Pricing reasonableness
#         - Completeness and relevance of fields
#         - Please Return only the score for each bidder and a final evaluator's summary paragraph explaining your rationale for the scoring distribution.
        
#         ### TENDER REQUIREMENTS JSON:
#         {tender_str}
#         ### Bidder RESPONSES
#         {st}

#         Output Format (Strict):
#         1. Bidder Scores:
#         - Bidder A: <score>
#         - Bidder B: <score>
#         - Bidder C: <score>
#         2. Overall Summary:
#         <A short comparative summary of the bidder responses, strengths, and weaknesses.>
#     """
#     return prompt

# def evaluate_with_groq(prompt):
#     chat_completion = client.chat.completions.create(
#         messages= [
#             {
#                 "role": "system",
#                 "content": "You are a government tender evaluation assistant using structured tender JSON data to help score bidder responses."
#             },
#             {
#                 "role": "user",
#                 "content": prompt
#             }
#         ],
#         model="llama-3.1-8b-instant"
#     )
#     response = chat_completion.choices[0].message.content
#     return response

# def response_evaluation():
#     tender_json = load_json(TENDER_FILE)
#     bidder_json=[]
#     for j in range(bid_no):
#       bidder_json.append(load_json(BIDDER_FILES[j]))

#     tender_str = format_json_as_text(tender_json)
#     bidder_str=[]
#     for j in range(bid_no):
#       bidder_str.append(format_json_as_text(bidder_json[j]))


#     prompt = construct_prompt(tender_str, bidder_str)
#     result = evaluate_with_groq(prompt)

#     print("\n=== Evaluation Result ===\n")
#     print(result)


# --------------------------------------------------------------------------------------------------------

