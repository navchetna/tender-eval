import os
from dotenv import load_dotenv
from comps.parsers.tree import Tree
from comps.parsers.treeparser import TreeParser

load_dotenv()

# Path to your PDF file
# pdf_path = os.environ("PDF_PATH")
pdf_path = "/home/raghu-intel/Ervin/test-ocr/control-center-bid-separated.pdf"

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


tree=parse_pdf(pdf_path)





