import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY= os.getenv('GROQ_API_KEY')

# Replace 'path/to/your_document.txt' with the actual path to your file
file_path = '/home/intel/kubernetes_files/aayush/Tender-Eval/comps/Search/out/tender-command-control/toc.txt' 

# Questions to ask the LLM
question1 = "Return only the number and text which best describes technical compliance? The output is just this without any other text: 1.2.2 Technical Requirements"
question2 = "Return only the number and text which best describes price? Example output is just this  without any other text: 1.4 Price Bid Evaluation"

# Function to read file content
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
def extract_answers_after_question_lines(response_text):
    answers = []
    lines = response_text.strip().split('\n')
    
    found_question = False
    for line in lines:
        if found_question:
            # This line immediately follows a "Question" line
            if line.strip(): # Ensure the line is not empty
                answers.append(line.strip())
            found_question = False # Reset the flag
        
        # Check if the current line contains the word "Question"
        # Using a case-insensitive search
        if "Question" in line: # Or re.search(r'\bQuestion\b', line, re.IGNORECASE) for word boundary
            found_question = True
            
    return answers
# Main function
def ask_groq_with_file_content(file_path, questions):
    # Initialize the Groq client
    # It automatically looks for GROQ_API_KEY environment variable
    client = Groq()

    # Read the file content
    document_content = read_file_content(file_path)
    if document_content is None:
        return []

    # Combine the document content and the questions into a single user message
    # Groq API doesn't directly support file uploads as separate entities for chat completion
    # Instead, you'll need to include the file content directly in your prompt.
    user_message_content = f"Document Content:\n```\n{document_content}\n```\n\n"
    for i, q in enumerate(questions):
        user_message_content += f"Question {i+1}: {q}\n"
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": user_message_content,
                }
            ],
            model="llama3-8b-8192",  # Or other suitable Groq models like "llama3-70b-8192"
        )

        #print("\n--- Groq Response ---")
        output1=str(chat_completion.choices[0].message.content)
        #print(output1)
        #print(extract_answers_after_question_lines(output1))
        #print(f"\nPrompt Tokens: {chat_completion.usage.prompt_tokens}")
        #print(f"Completion Tokens: {chat_completion.usage.completion_tokens}")
        #print(f"Total Time: {chat_completion.usage.total_time} seconds")
        return(extract_answers_after_question_lines(output1))

    except Exception as e:
        print(f"An error occurred: {e}")
        return()
    

#if __name__ == "__main__":
#    ask_groq_with_file_content(file_path, [question1, question2])

answers=ask_groq_with_file_content(file_path, [question1, question2])
print(answers)
