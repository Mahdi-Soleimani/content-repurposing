import httpx
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from pydantic import BaseModel

from app.services.storage import storage_service

router = APIRouter()

class TestResponse(BaseModel):
    success: bool
    message: str
    details: str | None = None

@router.post("/youtube/cookies")
async def upload_youtube_cookies(file: UploadFile = File(...)):
    """Upload YouTube cookies file to secure object storage."""
    if not file.filename.endswith(".txt"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cookies must be a .txt file"
        )
    
    try:
        object_key = "secrets/youtube/cookies.txt"
        storage_service.upload_fileobj(
            file.file, 
            object_key, 
            content_type="text/plain"
        )
        return {"status": "success", "message": "Cookies uploaded successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload cookies: {str(e)}"
        )

@router.post("/youtube/test", response_model=TestResponse)
async def test_youtube_cookies():
    """Trigger a connection test on the source-worker to validate the cookies."""
    # The source-worker handles the actual yt-dlp execution
    worker_url = "http://source-worker:8002/youtube/test"
    
    try:
        async with httpx.AsyncClient() as client:
            # We use a POST request with a timeout to allow for yt-dlp execution
            response = await client.post(worker_url, timeout=30.0)
            
            if response.status_code == 200:
                data = response.json()
                return TestResponse(
                    success=data.get("success", False),
                    message=data.get("message", "Test completed"),
                    details=data.get("details")
                )
            else:
                return TestResponse(
                    success=False, 
                    message=f"Worker responded with HTTP {response.status_code}",
                    details=response.text
                )
    except httpx.RequestError as e:
        return TestResponse(
            success=False,
            message="Failed to contact source-worker",
            details=str(e)
        )
