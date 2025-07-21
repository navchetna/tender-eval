import json
import os
from groq import Groq

# Set your Groq API Key here
GROQ_API_KEY = ""

# Paths to JSON files
TENDER_FILE = "/home/intel/kubernetes_files/ervin/BPCL/tender-eval/comps/dataprep/json-outputs/tender-requirements.json"
BIDDER_FILE_1 = "/home/intel/kubernetes_files/ervin/BPCL/tender-eval/comps/dataprep/json-outputs/bidder-response-1.json"
BIDDER_FILE_2 = "/home/intel/kubernetes_files/ervin/BPCL/tender-eval/comps/dataprep/json-outputs/bidder-response-2.json"
BIDDER_FILE_3 = "/home/intel/kubernetes_files/ervin/BPCL/tender-eval/comps/dataprep/json-outputs/bidder-response-3.json"

client = Groq(api_key=GROQ_API_KEY)

def load_json(file_path):
    with open(file_path, "r") as f:
        return json.load(f)

def format_json_as_text(json_obj):
    return json.dumps(json_obj, indent=2)

def construct_prompt(tender_str, bidder_str_1, bidder_str_2, bidder_str_3):
    prompt = f"""
        You are participating in a government tender evaluation process.

        You will be provided:
        1. The Tender Requirements JSON structure — this defines all expected fields and compliance criteria. These fields may be present but contain empty or placeholder values.
        2. Multiple Bidder Response JSON documents, each in the same format as the tender, but filled in with actual bids from different vendors.

        Your tasks:
        - Evaluate each bidder's JSON response against the tender requirements.
        - Determine how well each bidder meets the requirements.
        - Score each bidder out of 100 based on:
        - Technical compliance
        - Pricing reasonableness
        - Completeness and relevance of fields
        - Return only the score for each bidder and a final evaluator’s summary paragraph explaining your rationale for the scoring distribution.
        
        ### TENDER REQUIREMENTS JSON:
        {tender_str}
        ### BIDDER RESPONSE JSON 1:
        {bidder_str_1}
        ### BIDDER RESPONSE JSON 2:
        {bidder_str_2}
        ### BIDDER RESPONSE JSON 3:
        {bidder_str_3}

        Output Format (Strict):
        1. 🏆 Scores:
        - Bidder A: <score>
        - Bidder B: <score>
        - Bidder C: <score>
        2. 📝 Summary:
        <A short comparative summary of the bidder responses, strengths, and weaknesses.>
    """
    return prompt


    # return f"""
    #     You are an expert evaluator assisting in a public tender process.

    #     You will be given two JSON strings:
    #     1. The Tender Requirements document: This contains all the technical and financial requirements. Each field will be present, but actual values will be left blank or null.
    #     2. The Bidder Response document: This contains the same structure but with values filled in by a participating bidder.

    #     Your job is to:
    #     - Compare the bidder response against the tender requirements line-by-line.
    #     - Evaluate if all mandatory requirements are met (especially under "Technical Compliance").
    #     - Score the bidder response out of 100 based on coverage, correctness, and alignment with tender needs.
    #     - Justify your score in detail.
    #     - Identify any MISSING fields that are required but not present in the bidder’s response.
    #     - Identify any EXTRA fields added by the bidder that were not requested in the tender.
    #     - Be thorough and professional in your analysis.

    #     ### TENDER REQUIREMENTS JSON:
    #     {tender_str}
    #     ### BIDDER RESPONSE JSON 1:
    #     {bidder_str}
    #     Now, please perform the evaluation and respond in the following structure:
    #     1. ✅ Compliance Summary
    #     2. 📊 Score (out of 100)
    #     3. 📝 Justification
    #     4. 🔍 Missing Fields
    #     5. ➕ Extra Fields
    # """
    

def evaluate_with_groq(prompt):
    chat_completion = client.chat.completions.create(
        messages= [
            {
                "role": "system",
                "content": "You are a government tender evaluation assistant using structured tender JSON data to help score bidder responses."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        model="llama-3.1-8b-instant"
    )
    response = chat_completion.choices[0].message.content
    # if response.status_code != 200:
    #     raise Exception(f"Error from Groq API")
    return response

def main():
    tender_json = load_json(TENDER_FILE)
    bidder_json_1 = load_json(BIDDER_FILE_1)
    bidder_json_2 = load_json(BIDDER_FILE_2)
    bidder_json_3 = load_json(BIDDER_FILE_3)

    tender_str = format_json_as_text(tender_json)
    bidder_str_1 = format_json_as_text(bidder_json_1)
    bidder_str_2 = format_json_as_text(bidder_json_2)
    bidder_str_3 = format_json_as_text(bidder_json_3)

    prompt = construct_prompt(tender_str, bidder_str_1, bidder_str_2, bidder_str_3)
    result = evaluate_with_groq(prompt)

    print("\n=== 🔍 Evaluation Result ===\n")
    print(result)

if __name__ == "__main__":
    main()