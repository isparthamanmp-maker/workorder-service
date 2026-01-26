# src/services/minio_service.py
import os
import io
from typing import Optional, Tuple
from minio import Minio
from minio.error import S3Error
from fastapi import HTTPException, Response
from fastapi.responses import StreamingResponse

class MinioService:
    """Service to handle MinIO file operations"""
    
    def __init__(self):
        self.minio_client = Minio(
            endpoint="10.10.1.7:9000",
            access_key="minioadmin",
            secret_key="StrongPasswordHere123",
            secure=False
        )
        self.bucket_name = "workorder"
    
    def get_file(self, object_path: str) -> Tuple[Optional[bytes], Optional[str], Optional[int]]:
        """
        Get file from MinIO by object path
        
        Args:
            object_path: Full path to the object (e.g., "2026/01/26/Work_Order_0024_WOR_IT_NMP_N_2026_2026-01-12.pdf")
        
        Returns:
            Tuple of (file_data, content_type, file_size) or (None, None, None) if not found
        """
        try:
            # Get object info
            stat = self.minio_client.stat_object(self.bucket_name, object_path)
            
            # Get object data
            response = self.minio_client.get_object(self.bucket_name, object_path)
            file_data = response.read()
            response.close()
            response.release_conn()
            
            return file_data, stat.content_type, stat.size
            
        except S3Error as e:
            if e.code == "NoSuchKey":
                print(f"File not found: {object_path}")
                return None, None, None
            else:
                print(f"Error getting file from MinIO: {e}")
                raise HTTPException(status_code=500, detail=f"Error retrieving file: {str(e)}")
        except Exception as e:
            print(f"Unexpected error getting file from MinIO: {e}")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    
    def get_file_streaming(self, object_path: str) -> Optional[StreamingResponse]:
        """
        Get file from MinIO as streaming response
        
        Args:
            object_path: Full path to the object
        
        Returns:
            StreamingResponse or None if not found
        """
        try:
            # Get object info
            stat = self.minio_client.stat_object(self.bucket_name, object_path)
            
            # Get object as streaming response
            response = self.minio_client.get_object(self.bucket_name, object_path)
            
            def iterfile():
                for chunk in response.stream(amt=1024*1024):  # 1MB chunks
                    yield chunk
                response.close()
                response.release_conn()
            
            # Extract filename from object path
            filename = os.path.basename(object_path)
            
            return StreamingResponse(
                iterfile(),
                media_type=stat.content_type,
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Content-Length": str(stat.size)
                }
            )
            
        except S3Error as e:
            if e.code == "NoSuchKey":
                print(f"File not found: {object_path}")
                return None
            else:
                print(f"Error getting file from MinIO: {e}")
                raise HTTPException(status_code=500, detail=f"Error retrieving file: {str(e)}")
        except Exception as e:
            print(f"Unexpected error getting file from MinIO: {e}")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    
    def list_files(self, prefix: str = "") -> list:
        """
        List files in MinIO bucket with optional prefix
        
        Args:
            prefix: Path prefix to filter files (e.g., "2026/01/26/")
        
        Returns:
            List of file objects
        """
        try:
            objects = self.minio_client.list_objects(
                self.bucket_name, 
                prefix=prefix,
                recursive=True
            )
            
            files = []
            for obj in objects:
                files.append({
                    "name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified,
                    "etag": obj.etag
                })
            
            return files
            
        except Exception as e:
            print(f"Error listing files from MinIO: {e}")
            raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")
    
    def delete_file(self, object_path: str) -> bool:
        """
        Delete file from MinIO
        
        Args:
            object_path: Full path to the object
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.minio_client.remove_object(self.bucket_name, object_path)
            return True
        except S3Error as e:
            print(f"Error deleting file from MinIO: {e}")
            return False
    
    def file_exists(self, object_path: str) -> bool:
        """
        Check if file exists in MinIO
        
        Args:
            object_path: Full path to the object
        
        Returns:
            True if file exists, False otherwise
        """
        try:
            self.minio_client.stat_object(self.bucket_name, object_path)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            raise


# Create a singleton instance
minio_service = MinioService()