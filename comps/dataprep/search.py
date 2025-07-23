import re
import os
import numpy as np
import pandas as pd
from io import StringIO
from comps.dataprep.pdfparse import tree
from comps.parsers.tree import Tree
from comps.parsers.text import Text
from comps.parsers.table import Table
from comps.parsers.treeparser import TreeParser



# compliance_sections = {'technical': '3;1.2.2 Technical Requirements', 'price': '2;1.4 Price Bid Evaluation'}

bidder_response_sections = {'technical': '2;3. Response to Technical Requirements (Ref: Annexure1, Section1.2.2)', 'price': '2;6. Price Bid Submission (Ref: Annexure1, Section1.4)'}

def fuzzy_matches(heading, query):
    """
    Checks if the heading matches the query using fuzzy matching.
    Returns True if the match score is above a threshold, otherwise False.
    """
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

    # delete the first row and first and last columns as they are the "|" separators
    df = df.iloc[1:]
    df = df.drop(df.columns[[0, -1]], axis=1)
    # clean out the column names
    df.columns = [col.strip() for col in df.columns]
    #print (df)
    print("DataFrame created from markdown content")
    df.to_excel(f'{section_title}.xlsx', index=False)
    print(f"DataFrame saved to '{section_title}.xlsx'")

    return df


if __name__ == "__main__":
    print("Starting PDF parsing and data retrieval...")

    for section_number, section_title in bidder_response_sections.items():
        section_title = section_title[2:] if section_title else None

        target_node = find_node_by_level_or_title(tree.rootNode, section_title)
        markdown_content = retrieve_from_pdf(target_node)

        df = markdown_to_df(markdown_content, section_title)

    
print("End")
    

