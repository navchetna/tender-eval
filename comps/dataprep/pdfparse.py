import os
from dotenv import load_dotenv
from comps.parsers.tree import Tree
from comps.parsers.treeparser import TreeParser

load_dotenv()

pdf_path = os.environ.get("PDF_PATH")
print("Parsing pdf: ", pdf_path)
# pdf_path = "/home/ritik-intel/Ervin/tender-doc.pdf"

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


tree = parse_pdf(pdf_path)





