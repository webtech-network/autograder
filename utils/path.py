import os

class Path:
    def __init__(self, root, mid):
        self.root = root
        self.mid = mid
        self.base_path = os.path.dirname(self.root)
    
    def getFilePath(self, end):
        return os.path.join(self.base_path, self.mid, end)
