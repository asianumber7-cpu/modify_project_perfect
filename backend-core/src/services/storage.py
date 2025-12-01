import abc
import os
import shutil
import boto3
from botocore.exceptions import ClientError
from typing import Optional
from fastapi import UploadFile
from src.config.settings import settings

class StorageService(abc.ABC):
    """
    Abstract Base Class for Storage Strategies
    """
    @abc.abstractmethod
    async def upload(self, file: UploadFile, destination: str) -> str:
        """Upload a file and return its path/key"""
        pass

    @abc.abstractmethod
    async def delete(self, path: str) -> bool:
        """Delete a file"""
        pass

    @abc.abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if file exists"""
        pass

    @abc.abstractmethod
    def generate_presigned_url(self, path: str, expiration: int = 3600) -> str:
        """Generate a temporary accessible URL"""
        pass


class LocalStorage(StorageService):
    def __init__(self):
        self.base_path = settings.LOCAL_STORAGE_PATH
        os.makedirs(self.base_path, exist_ok=True)

    async def upload(self, file: UploadFile, destination: str) -> str:
        full_path = os.path.join(self.base_path, destination)
        directory = os.path.dirname(full_path)
        os.makedirs(directory, exist_ok=True)
        
        try:
            with open(full_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            return destination
        except Exception as e:
            # 실무에서는 로깅 처리 필수
            print(f"Local upload failed: {e}")
            raise e

    async def delete(self, path: str) -> bool:
        full_path = os.path.join(self.base_path, path)
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
        return False

    async def exists(self, path: str) -> bool:
        full_path = os.path.join(self.base_path, path)
        return os.path.exists(full_path)

    def generate_presigned_url(self, path: str, expiration: int = 3600) -> str:
        # Local 환경에서는 정적 파일 서빙 URL 반환 (개발용)
        # Nginx나 FastAPI StaticFiles 설정 필요
        return f"http://localhost:8000/static/{path}"


class S3Storage(StorageService):
    def __init__(self):
        self.client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.bucket = settings.AWS_BUCKET_NAME

    async def upload(self, file: UploadFile, destination: str) -> str:
        try:
            self.client.upload_fileobj(
                file.file,
                self.bucket,
                destination,
                ExtraArgs={
                    'ServerSideEncryption': 'AES256', # 보안 요구사항 충족
                    'ContentType': file.content_type
                }
            )
            return destination
        except ClientError as e:
            print(f"S3 upload failed: {e}")
            raise e

    async def delete(self, path: str) -> bool:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=path)
            return True
        except ClientError:
            return False

    async def exists(self, path: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=path)
            return True
        except ClientError:
            return False

    def generate_presigned_url(self, path: str, expiration: int = 3600) -> str:
        try:
            response = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': path},
                ExpiresIn=expiration
            )
            return response
        except ClientError:
            return ""

def get_storage_service() -> StorageService:
    if settings.STORAGE_TYPE == "s3":
        return S3Storage()
    return LocalStorage()