from ..metrics.data_fetcher.huggingface import get_huggingface_model_data
from ..cli.schema import default_ndjson
import re

class Artifact():
    def __init__(self, url):
        self.url = url

class Model(Artifact):
    def __init__(self, url):
        super().__init__(url)
        self.type = "model"
        hf_match = re.match(r"https?://huggingface\.co/([^/]+)/([^/]+)", self.url)
        if hf_match:
            self.name = hf_match.group(2)
        else:
            raise ValueError("Invalid model URL")
        self.id = hash(self.url)
        
        


class Dataset(Artifact):
    def __init__(self, url):
        super().__init__(url)
        self.type = "dataset"

    def get_metadata(self):
        ndjson = default_ndjson(self.url, category="dataset")
        self.name = ndjson['name']


class Code(Artifact):
    def __init__(self, url):
        super().__init__(url)
        self.type = "code"

    def get_metadata(self):
        ndjson = default_ndjson(self.url, category="code")
        self.name = ndjson['name']

