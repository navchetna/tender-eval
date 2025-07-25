import json
import os
from groq import Groq
import subprocess

# Set your Groq API Key here
GROQ_API_KEY = ""

# Paths to JSON files
TENDER_FILE = "/home/aayush/tender-eval/comps/dataprep/json-outputs/tender-requirements.json"
#Dynamically taking in the Bids!
directory="/home/aayush/tender-eval/comps/dataprep/json-outputs"
lst=os.listdir(directory)
bid_no=int(len(lst)/3)
#bid_no = int(3)
BIDDER_FILES = []

for j in range(bid_no):
    k = j + 1
    BIDDER_FILES.append(f"/home/aayush/tender-eval/comps/dataprep/json-outputs/bidder-response-{k}.json")


client = Groq(api_key=GROQ_API_KEY)

def load_json(file_path):
    with open(file_path, "r") as f:
        return json.load(f)

def format_json_as_text(json_obj):
    return json.dumps(json_obj, indent=2)

def construct_prompt(tender_str, bidder_str):
    st=str("")
    for j in range(bid_no):
            st+=("BIDDER RESPONSE JSON "+str(j+1)+"\n")
            st+=(bidder_str[j]) 
    prompt = f"""
        You are participating in a government tender evaluation process.

        You will be provided:
        1. The Tender Requirements JSON structure — this defines all expected fields and compliance criteria. These fields may be present but contain empty or placeholder values.
        2. Multiple Bidder Response JSON documents, each in the same format as the tender, but filled in with actual bids from different vendors.

        Your tasks:
        - Please Evaluate each bidder's JSON response against the tender requirements.
        - Please Determine how well each bidder meets the requirements.
        - Please Score each bidder out of 100 based on:
        - Technical compliance
        - Pricing reasonableness
        - Completeness and relevance of fields
        - Please Return only the score for each bidder and a final evaluator’s summary paragraph explaining your rationale for the scoring distribution.
        
        ### TENDER REQUIREMENTS JSON:
        {tender_str}
        ### Bidder RESPONSES
        {st}

        Output Format (Strict):
        1. ðŸ† Scores:
        - Bidder A: <score>
        - Bidder B: <score>
        - Bidder C: <score>
        2. ðŸ“ Summary:
        <A short comparative summary of the bidder responses, strengths, and weaknesses.>
    """
    return prompt

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
    return response
def evaluate_with_ollama(prompt, model="deepseek-r1:1.5b"):
    try:
        # Run the Ollama CLI command
        result = subprocess.run(
            ["ollama", "run", model],
            input=prompt,  
            capture_output=True,
            text=True,
            check=True  # Raise an exception for non-zero exit codes
        )

        # Check if the command was successful
        if result.returncode == 0:
            return result.stdout.strip()  # Return the output
        else:
            return f"Error: {result.stderr.strip()}"  # Return the error message
    except FileNotFoundError:
        return "Ollama CLI is not installed or not found in PATH."
def main():
    tender_json = load_json(TENDER_FILE)
    bidder_json=[]
    for j in range(bid_no):
      bidder_json.append(load_json(BIDDER_FILES[j]))

    tender_str = format_json_as_text(tender_json)
    bidder_str=[]
    for j in range(bid_no):
      bidder_str.append(format_json_as_text(bidder_json[j]))


    prompt = construct_prompt(tender_str, bidder_str)
    result = evaluate_with_groq(prompt)
    #result = evaluate_with_ollama(prompt)
    print("\n=== ðŸ” Evaluation Result ===\n")
    print(result)

if __name__ == "__main__":
    main()
