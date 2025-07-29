import re
import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

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
    

if __name__ == "__main__":
    
    GROQ_API_KEY= os.getenv('GROQ_API_KEY')
    TOC_FILE_PATH = "/home/intel/kubernetes_files/aayush/Tender-Eval/comps/Search/out/control-center-bid-1/toc.txt"
    
    sections_str = ask_groq_with_file_content(TOC_FILE_PATH)
    compliance_sections = json.loads(sections_str)
    print(compliance_sections)
