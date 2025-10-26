from ..metrics.data_fetcher.huggingface import get_huggingface_model_data
from ..cli.schema import default_ndjson
import re
import sys

class Artifact():
    def __init__(self, url):
        self.url = url

class Model(Artifact):
    def __init__(self, url):
        super().__init__(url)
        self.type = "model"
        ndjson = default_ndjson(self.url, category=self.type)
        self.name = ndjson['name']
        self.id = str(hash(self.url) + sys.maxsize + 1)
        self.metadata = {'name': self.name, 'id': self.id, 'type': self.type}
        
class Dataset(Artifact):
    def __init__(self, url):
        super().__init__(url)
        self.type = "dataset"
        ndjson = default_ndjson(self.url, category=self.type)
        self.name = ndjson['name']
        self.id = str(hash(self.url) + sys.maxsize + 1)
        self.metadata = {'name': self.name, 'id': self.id, 'type': self.type}


class Code(Artifact):
    def __init__(self, url):
        super().__init__(url)
        self.type = "code"
        ndjson = default_ndjson(self.url, category=self.type)
        self.name = ndjson['name']
        self.id = str(hash(self.url) + sys.maxsize + 1)
        self.metadata = {'name': self.name, 'id': self.id, 'type': self.type}

