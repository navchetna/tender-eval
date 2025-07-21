class OCRText:
    def __init__(self, content, image_filename, parentNode=None):
        """
        content: OCR string
        image_filename: original image file name
        parentNode: Node object
        """
        self.content = content
        self.image_filename = image_filename
        self.parentNode = parentNode
