import pandas as pd
import json

def excel_to_technical_compliance_json(excel_file):
    # Read the Excel file
    df = pd.read_excel(excel_file, header=None)

    # Initialize the nested structure
    technical_json = {"Technical Compliance": {}}

    # Iterate over each row
    for _, row in df.iterrows():
        key = str(row[0]).strip() if pd.notna(row[0]) else None
        if key:
            value = str(row[1]) if len(row) > 1 and pd.notna(row[1]) else ""
            technical_json["Technical Compliance"][key] = value.strip()

    return technical_json

# Replace 'technical_input.xlsx' with your Excel file path
excel_file = '/home/intel/kubernetes_files/ervin/BPCL/tender-eval/comps/dataprep/3._Response_to_Technical_Requirements_(Ref:_Annexure1,_Section1.2.2).xlsx'
result = excel_to_technical_compliance_json(excel_file)

# Optional: write to a JSON file
with open('/home/intel/kubernetes_files/ervin/BPCL/tender-eval/comps/dataprep/technical_response.json', 'w') as f:
    json.dump(result, f, indent=4)

# Print the result
print(json.dumps(result, indent=4))
