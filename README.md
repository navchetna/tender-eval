# Tender Evaluation

Purpose: Large Companies set up tenders for the procurement of infrastructure needed by them. In order to reduce bias and select the best bid offered by other companies a streamlined system needs to be implemented.

This would require the comparison of the requirements made in the tender to the proposal by the bid. This would determine the degree of technical compliance. Likewise the price needs to be evaluated to ensure the most cost effective solution is selected.

Thus we implemented a solution to this problem by utilizing pdf parsing coupled with a LLM to give an explainable solution by parsing the tender pdf to create a tree structure along with a file containing a table of contents. We allowed the LLM to select the elements on the TOC that best match the technical compliance and pricing.

We then search the tree to find those tables and convert them to pandas dataframe. This is saved to an excel file for reference and explainability. This process is repeated for the bidder file whose relevant information is condensed into an excel file.

We cross examine the tender’s file with each bidder to take the relevant rows and package them into a json file which can be read by the LLM to compare between bidders and explain why some were selected and why some were not.

