import pandas as pd
import json

def excel_to_nested_json(excel_file):
    # Read the Excel file
    df = pd.read_excel(excel_file)

    # Remove rows with missing 'Item' values
    df = df.dropna(subset=["Item"])

    # Initialize the nested structure
    nested_json = {"Price Compliance": {}}

    for _, row in df.iterrows():
        item_name = str(row["Item"]).strip()
        nested_json["Price Compliance"][item_name] = {
            "Unit": str(row["Unit"]).strip(),
            "Qty": str(row["Qty"]).strip(),
            "Unit Cost": str(row["Unit Cost"]).strip(),
            "Total Cost": str(row["Total Cost"]).strip()
        }

    return nested_json

# Replace 'input.xlsx' with your Excel file path
excel_file = '/home/intel/kubernetes_files/ervin/BPCL/tender-eval/comps/dataprep/1.4_Price_Bid_Evaluation.xlsx'
result = excel_to_nested_json(excel_file)

# Optional: write to a JSON file
with open('/home/intel/kubernetes_files/ervin/BPCL/tender-eval/comps/dataprep/price_bid_evaluation.json', 'w') as f:
    json.dump(result, f, indent=4)

# Print the result
print(json.dumps(result, indent=4))
