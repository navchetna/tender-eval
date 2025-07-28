import pandas as pd
import json
import re

def excel_to_price_compliance_json(
    excel_file,
    sheet_name=0,
    root_key='Data',
    normalise_headers=True,
    allow_fallback=False
):
    df = pd.read_excel(excel_file, sheet_name=sheet_name, dtype=str)

    def _clean_header(h):
        h = str(h).strip()
        h = re.sub(r'\s+', ' ', h)
        return h.title()

    if normalise_headers:
        df.columns = [_clean_header(c) for c in df.columns]

    key_column = next((c for c in df.columns if c.lower() == 'item'), None)
    if key_column is None:
        if allow_fallback:
            key_column = df.columns[0]
        else:
            raise KeyError("No column named 'Item' found in the sheet.")

    df = df.dropna(subset=[key_column])

    nested = {}

    for _, row in df.iterrows():
        item_name = str(row[key_column]).strip()
        payload = {
            col: ("" if pd.isna(val) else str(val).strip())
            for col, val in row.items()
            if col != key_column
        }
        nested[item_name] = payload

    return nested

def main():
    excel_file = '/home/ritik-intel/Ervin/tender-eval/comps/6._Price_Bid_Submission_(Ref:_Annexure1,_Section1.4).xlsx'
    output_file = '/home/ritik-intel/Ervin/price_response.json'
    
    json_data = excel_to_nested_json(
        excel_file,
        sheet_name=0,
        root_key='Price Compliance'
    )

    with open(output_file, 'w') as fh:
        json.dump(json_data, fh, indent=4)

    print(json.dumps(json_data, indent=4))
    print(f"\nJSON data has been written to: {output_file}")

if __name__ == "__main__":
    main()
