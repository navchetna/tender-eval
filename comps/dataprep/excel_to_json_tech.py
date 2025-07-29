import pandas as pd
import json

def excel_to_technical_compliance_json(excel_file):
    df = pd.read_excel(excel_file, header=None)

    technical_json = {}

    for _, row in df.iloc[1:].iterrows():
        key = str(row[0]).strip() if pd.notna(row[0]) else None
        if key:
            value = str(row[1]) if len(row) > 1 and pd.notna(row[1]) else ""
            technical_json[key] = value.strip()

    return technical_json

# print(json.dumps(result, indent=4))

def main():
    excel_file = '/home/ritik-intel/Ervin/tender-eval/comps/3._Response_to_Technical_Requirements_(Ref:_Annexure1,_Section1.2.2).xlsx'
    output_file = '/home/ritik-intel/Ervin/tender-eval/comps/technical_response.json'
    
    json_data = excel_to_technical_compliance_json(excel_file)

    with open(output_file, 'w') as fh:
        json.dump(json_data, fh, indent=4)

    print(json.dumps(json_data, indent=4))
    print(f"\nJSON data has been written to: {output_file}")

if __name__ == "__main__":
    main()

