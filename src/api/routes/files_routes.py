# src/api/routes/files_routes.py
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from fastapi.responses import StreamingResponse, Response
from typing import Optional
from src.services.minio_service import minio_service
import urllib.parse

router = APIRouter(prefix="/api/v1/files", tags=["files"])

@router.get("/download/{file_path:path}")
def download_file(
    file_path: str = Path(..., description="Path to the file in MinIO (e.g., 2026/01/26/filename.pdf)"),
    inline: bool = Query(False, description="If True, display in browser; if False, download as attachment")
):
    """
    Download a file from MinIO storage
    
    Example:
    GET /api/v1/files/download/2026/01/26/Work_Order_0024_WOR_IT_NMP_N_2026_2026-01-12.pdf
    """
    try:
        # URL decode the file path
        file_path = urllib.parse.unquote(file_path)
        
        # Get streaming response
        streaming_response = minio_service.get_file_streaming(file_path)
        
        if not streaming_response:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Modify headers if inline viewing is requested
        if inline:
            headers = dict(streaming_response.headers)
            if "Content-Disposition" in headers:
                # Remove "attachment" to allow inline viewing
                content_disp = headers["Content-Disposition"]
                if 'attachment' in content_disp:
                    headers["Content-Disposition"] = content_disp.replace('attachment', 'inline')
            streaming_response.headers = headers
        
        return streaming_response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")

@router.get("/preview/{file_path:path}")
def preview_file(
    file_path: str = Path(..., description="Path to the file in MinIO")
):
    """
    Preview a file in browser (forces inline display)
    
    Example:
    GET /api/v1/files/preview/2026/01/26/Work_Order_0024_WOR_IT_NMP_N_2026_2026-01-12.pdf
    """
    return download_file(file_path, inline=True)

@router.get("/list")
def list_files(
    prefix: Optional[str] = Query("", description="Prefix to filter files (e.g., 2026/01/26/)")
):
    """
    List files in MinIO bucket
    
    Example:
    GET /api/v1/files/list?prefix=2026/01/26/
    """
    try:
        files = minio_service.list_files(prefix)
        return {
            "bucket": minio_service.bucket_name,
            "prefix": prefix,
            "file_count": len(files),
            "files": files
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")

@router.delete("/{file_path:path}")
def delete_file(
    file_path: str = Path(..., description="Path to the file in MinIO")
):
    """
    Delete a file from MinIO
    
    Example:
    DELETE /api/v1/files/2026/01/26/Work_Order_0024_WOR_IT_NMP_N_2026_2026-01-12.pdf
    """
    try:
        file_path = urllib.parse.unquote(file_path)
        
        if not minio_service.file_exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        success = minio_service.delete_file(file_path)
        
        if success:
            return {"message": "File deleted successfully", "file_path": file_path}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete file")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")

@router.head("/{file_path:path}")
def check_file_exists(
    file_path: str = Path(..., description="Path to the file in MinIO")
):
    """
    Check if a file exists in MinIO (HEAD request)
    
    Example:
    HEAD /api/v1/files/2026/01/26/Work_Order_0024_WOR_IT_NMP_N_2026_2026-01-12.pdf
    """
    try:
        file_path = urllib.parse.unquote(file_path)
        
        if minio_service.file_exists(file_path):
            return Response(status_code=200)
        else:
            return Response(status_code=404)
            
    except Exception as e:
        return Response(status_code=500)