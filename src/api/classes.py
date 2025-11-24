# from ..metrics.data_fetcher.huggingface import get_huggingface_model_data
# from ..cli.schema import default_ndjson
# from ..url_parsers.url_type_handler import handle_url
# from ..cli.validate import validate_ndjson
# from src.logger import get_logger
# from .auth import authenticate, getPermissionLevel
# from src.metrics.data_fetcher.huggingface import download_hf_model
# from .s3 import upload_file_to_s3, get_download_link
# import os
# import zipfile

# logger = get_logger("api.app")
# import re
# import sys
# import uuid
# from src.logger import get_logger

# logger = get_logger("api.app")

# class BaseArtifact():
#     def __init__(self, url, name=None):
#         self.url = url
#         self.name = name
#         self.download_url = ""
#         self.id = int(uuid.uuid4().int % 1e11)


# class Model(BaseArtifact):
#     def __init__(self, url, name=None):
#         super().__init__(url, name)
#         self.type = "model"
#         hf_match = re.match(r"https?://huggingface\.co/([^/]+)/([^/]+)", url)
#         if self.name is None and not hf_match:
#             raise ValueError("Name must be provided for models.")
#         self.name = self.name if self.name else hf_match.group(2)
#         self.metadata = {'name': self.name, 'id': self.id, 'type': self.type}
#         self.ndjson = {}
#         self.code_url = ""
#         self.dataset_url = ""
#         self.download_link = ""
#         #TODO: determine code and dataset objects linked form registry
#         try:
#             self.rate()
#         except Exception as e:
#             logger.error(f"Error rating model during initialization: {e}")
#             raise RuntimeError("Failed to rate model during initialization")
        
#         #TODO: uncomment when code and dataset linking is available
#         # if not newArtifact.check_ingestible():
#             #     return jsonify({'description': 'Artifact is not registered due to the disqualified rating.'}), 424
        
#         try:
#             self.send_to_bucket()
#         except Exception as e:
#             logger.error(f"Error sending model to bucket: {e}")
#             raise RuntimeError("Failed to send model to bucket")
        
#     def check_ingestible(self) -> bool:
#         if self.ndjson == {}:
#             return False
        
#         # print(self.ndjson)
        
#         for key in self.ndjson:
#             if not key.endswith("_latency") and key != "name" and key != "category":
#                 if isinstance(self.ndjson[key], dict):
#                     for subkey in self.ndjson[key]:
#                         if self.ndjson[key][subkey] < 0.5:
#                             return False
#                 # print(self.ndjson[key])
#                 if self.ndjson[key] < 0.5:
#                     return False
#         return True
      
#     def rate(self) -> bool:
#         if self.ndjson != {}:
#             logger.info("Model already rated, skipping re-rating.")
#             return True
        
#         logger.info(f"Rating model artifact {self.id} with name {self.name}")
#         try:
#             raw_ndjson = handle_url({0: [self.code_url, self.dataset_url, self.url]})[0]
#         except Exception as e:
#             logger.error(f"Error handling URL for rating: {e}")
#             return False
#         if(validate_ndjson(raw_ndjson)):
#             self.ndjson = raw_ndjson
#             self.ndjson.update({'name': self.name, 'category': self.type})
        
#         logger.info(f"Completed rating for model artifact {self.id} with name {self.name}")
#         return True
    
#     def send_to_bucket(self):
#         """Download model files and store them in S3."""
#         logger.info(f"Downloading model files for artifact {self.id} from {self.url}")
#         local_dir = download_hf_model(self.url, cache_dir="./hf_cache")
#         logger.info(f"Downloaded model files to {local_dir}")
        
#         zout = zipfile.ZipFile(f"{local_dir}/{self.id}.zip", "w")
#         for root, _, files in os.walk(local_dir):
#             for file in files:
#                 if file == f"{self.id}.zip":
#                     continue  # Skip adding the zip file itself
#                 local_file_path = os.path.join(root, file)
#                 rel_path = os.path.relpath(local_file_path, local_dir)
#                 logger.debug(f"Adding {local_file_path} as {rel_path} to zip")
#                 zout.write(local_file_path, arcname=rel_path)
#         zout.close()
        
#         self.cost = os.path.getsize(f"{local_dir}/{self.id}.zip") / (1024 * 1024)  # size in MB

#         success = upload_file_to_s3(f"{local_dir}/{self.id}.zip", f"{self.id}.zip")
#         if not success:
#             logger.error(f"Failed to upload {self.id}.zip to S3")
#             raise RuntimeError(f"Failed to upload {self.id}.zip to S3")
        
#         logger.info(f"Uploaded zip file {self.id}.zip to S3")
        
#         os.system(f"rm -rf {local_dir}/{self.id}.zip")

#         self.download_link = get_download_link(self.id)


                
# class Dataset(BaseArtifact):
#     def __init__(self, url, name=None):
#         super().__init__(url, name)
#         self.ndjson = {}
#         self.code_url = ""
#         self.dataset_url = ""
#         #TODO: determine code and dataset objects linked form registry


# class Code(BaseArtifact):
#     def __init__(self, url, name=None):
#         super().__init__(url, name)
#         self.type = "code"
#         self.metadata = {'name': self.name, 'id': self.id, 'type': self.type}

