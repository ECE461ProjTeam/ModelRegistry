from ..metrics.data_fetcher.huggingface import get_huggingface_model_data
from ..cli.schema import default_ndjson
import re
import sys
import uuid
from src.logger import get_logger

logger = get_logger("api.app")

class Artifact():
    def __init__(self, url, name=None):
        self.url = url
        self.name = name
        self.download_url = ""
        self.id = str(int(uuid.uuid4().int % 1e9))


class Model(Artifact):
    def __init__(self, url, name=None):
        super().__init__(url, name)
        self.type = "model"
        hf_match = re.match(r"https?://huggingface\.co/([^/]+)/([^/]+)", url)
        if self.name is None and hf_match:
            self.name = hf_match.group(2)
        else:
            raise ValueError("Invalid model URL")
        self.metadata = {'name': self.name, 'id': self.id, 'type': self.type}
                
class Dataset(Artifact):
    def __init__(self, url, name=None):
        super().__init__(url, name)
        self.type = "dataset"
        self.metadata = {'name': self.name, 'id': self.id, 'type': self.type}


class Code(Artifact):
    def __init__(self, url, name=None):
        super().__init__(url, name)
        self.type = "code"
        self.metadata = {'name': self.name, 'id': self.id, 'type': self.type}

