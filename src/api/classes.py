from ..metrics.data_fetcher.huggingface import get_huggingface_model_data
from ..cli.schema import default_ndjson
from ..url_parsers.url_type_handler import handle_url
from ..cli.validate import validate_ndjson
from src.logger import get_logger
from .auth import authenticate, getPermissionLevel

logger = get_logger("api.app")
import re
import sys
import uuid
from src.logger import get_logger

logger = get_logger("api.app")

class BaseArtifact():
    def __init__(self, url, name=None):
        self.url = url
        self.name = name
        self.download_url = ""
        self.id = int(uuid.uuid4().int % 1e11)


class Model(BaseArtifact):
    def __init__(self, url, name=None):
        super().__init__(url, name)
        self.type = "model"
        hf_match = re.match(r"https?://huggingface\.co/([^/]+)/([^/]+)", url)
        if self.name is None and not hf_match:
            raise ValueError("Name must be provided for models.")
        self.name = self.name if self.name else hf_match.group(2)
        self.metadata = {'name': self.name, 'id': self.id, 'type': self.type}
        
    def check_ingestible(self) -> bool:
        if self.ndjson == {}:
            return False
        
        print(self.ndjson)
        
        for key in self.ndjson:
            if not key.endswith("_latency") and key != "name" and key != "category":
                if isinstance(self.ndjson[key], dict):
                    for subkey in self.ndjson[key]:
                        if self.ndjson[key][subkey] < 0.5:
                            return False
                print(self.ndjson[key])
                if self.ndjson[key] < 0.5:
                    return False
        return True
      
    def rate(self) -> bool:
        if self.ndjson != {}:
            logger.info("Model already rated, skipping re-rating.")
            return True
        
        logger.info(f"Rating model artifact {self.id} with name {self.name}")
        try:
            raw_ndjson = handle_url({0: [self.code_url, self.dataset_url, self.url]})[0]
        except Exception as e:
            logger.error(f"Error handling URL for rating: {e}")
            return False
        if(validate_ndjson(raw_ndjson)):
            self.ndjson = raw_ndjson
            self.ndjson.update({'name': self.name, 'category': self.type})
        
        logger.info(f"Completed rating for model artifact {self.id} with name {self.name}")
        return True

                
class Dataset(BaseArtifact):
    def __init__(self, url, name=None):
        super().__init__(url, name)
        self.ndjson = {}
        self.code_url = ""
        self.dataset_url = ""
        #TODO: determine code and dataset objects linked form registry


class Code(BaseArtifact):
    def __init__(self, url, name=None):
        super().__init__(url, name)
        self.type = "code"
        self.metadata = {'name': self.name, 'id': self.id, 'type': self.type}

