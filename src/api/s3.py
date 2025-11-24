import os
import boto3
from src.logger import get_logger

logger = get_logger("api.s3")

BUCKET_NAME = os.environ.get("BUCKET_NAME")
s3_client = boto3.client('s3')

def upload_file_to_s3(file_name: str, artifact_id: str) -> bool:
    """Upload a file to an S3 bucket

    :param file_name: File to upload
    :param artifact_id: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """
    try:
        s3_client.upload_file(file_name, BUCKET_NAME, artifact_id)
    except Exception as e:
        logger.error(f"Error uploading file to S3: {e}")
        return False
    return True


def get_download_link(artifact_id: str) -> str:
    """Generate a download link for an artifact stored in S3."""
    return f"https://{BUCKET_NAME}.s3.amazonaws.com/{artifact_id}.zip"

def clear_s3_bucket():
    """Utility function to clear all objects in the S3 bucket. Use with caution."""
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(BUCKET_NAME)
    bucket.objects.all().delete()