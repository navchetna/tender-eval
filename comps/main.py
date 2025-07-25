import re
import os
import numpy as np
import pandas as pd
from io import StringIO
from dotenv import load_dotenv
from comps.parsers.tree import Tree
from comps.parsers.text import Text
from comps.parsers.table import Table
from comps.parsers.treeparser import TreeParser

load_dotenv()
# main.py calls pdfparse.tree
# the pdfparse script should loop through all pdfs and and return the tree for each
# the returned tree should then be sent to the rest of the pipeline 



# instead of a single path, this should take a directory and loop through files

## PART 1 create a tree in memory -> this also creates the .md and toc.txt
pdf_path = os.environ.get("PDF_PATH")
print("Parsing pdf: ", pdf_path)

def parse_pdf(pdf_path):
    # Create the Tree and parser
    tree = Tree(pdf_path)
    parser = TreeParser()
    # Populate the tree
    parser.populate_tree(tree)
    # Save hierarchy as text
    parser.generate_output_text(tree)
    # Save hierarchy as JSON
    parser.generate_output_json(tree)

    print("Parsing complete!")
    print(f"See outputs in: out/{tree.file.split('/')[-1].replace('.pdf','')}")
    return (tree)

tree = parse_pdf(pdf_path)

## PART 2 - Use the toc.txt to generate tech and price requirements

GROQ_API_KEY= os.getenv('GROQ_API_KEY')
TOC_FILE_PATH = "/home/intel/kubernetes_files/aayush/Tender-Eval/comps/Search/out/control-center-bid-1/toc.txt"

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
    


sections_str = ask_groq_with_file_content(TOC_FILE_PATH)
compliance_sections = json.loads(sections_str)


## Part 3 - Now we have a dictionary of requirements, both tech and price
## now we need to find the nodes in the tree that match these requirements
## once we find these, we extract those parts from the markdown and convert them into panda dataframes 

# compliance_sections = {'technical': '3;1.2.2 Technical Requirements', 'price': '2;1.4 Price Bid Evaluation'}
bidder_response_sections = {'technical': '2;3. Response to Technical Requirements (Ref: Annexure1, Section1.2.2)', 'price': '2;6. Price Bid Submission (Ref: Annexure1, Section1.4)'}

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
    df.to_excel(f'{section_title}.xlsx', index=False)
    print(f"DataFrame saved to '{section_title}.xlsx'")

    return df

for section_number, section_title in bidder_response_sections.items():
    section_title = section_title[2:] if section_title else None

    target_node = find_node_by_level_or_title(tree.rootNode, section_title)
    markdown_content = retrieve_from_pdf(target_node)

    df = markdown_to_df(markdown_content, section_title)

# PART 4 - Now we have the df for both technical and price compliance for a particular pdf -> converted to excel sheets
# 2 excel sheets for each pdf
# convert these excel sheets into json files

# how?:
# call the excel_to_json_price and excel_to_json_technical functions
# with the paths of the excel files

# TO DO--------------------------------


 
# PART 5 - call the evaluate_responses function that would ideally take multiple json strings
# and evaluate the responses based on the scores
