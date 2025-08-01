import os
from comps.parsers.node import Node

BASE_OUTPUT_DIR = "out"

class Tree:
    def __init__(self, file):
        self.rootNode = Node('0', "root", BASE_OUTPUT_DIR)
        self.file = file
    