"""Application uploader for uploading GEDCOM to hosted genealogy application."""
import httpx
from typing import Optional, Dict, Any
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ApplicationUploader:
    """Upload GEDCOM files to the hosted genealogy application."""
    
    def __init__(
        self,
        app_url: str,
        api_key: Optional[str] = None,
        upload_timeout: int = 30,
        parse_timeout: int = 300,
        enabled: bool = True
    ):
        """
        Initialize application uploader.
        
        Args:
            app_url: Base URL of the hosted application (e.g., https://korzen.vovcia.net)
            api_key: Optional API key for authentication
            upload_timeout: Timeout for upload requests in seconds
            parse_timeout: Timeout for parse requests in seconds
            enabled: Whether application upload is enabled
        """
        self.app_url = app_url.rstrip('/') if app_url else None
        self.api_key = api_key
        self.upload_timeout = upload_timeout
        self.parse_timeout = parse_timeout
        self.enabled = enabled and app_url is not None
        
        if self.enabled:
            logger.info(f"ApplicationUploader initialized with app_url: {self.app_url}")
        else:
            logger.info("ApplicationUploader disabled (no app_url configured)")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for requests."""
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    def upload_gedcom(
        self,
        gedcom_content: str,
        filename: str,
        document_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload GEDCOM file to the hosted application.
        
        Args:
            gedcom_content: GEDCOM file content as string
            filename: Name of the GEDCOM file
            document_id: Optional document ID for tracking
        
        Returns:
            Dictionary with upload results including file_id
        
        Raises:
            Exception: If upload fails or is disabled
        """
        if not self.enabled:
            logger.warning("Application upload is disabled, skipping")
            return {
                "success": False,
                "skipped": True,
                "reason": "Application upload disabled"
            }
        
        try:
            upload_url = f"{self.app_url}/upload"
            logger.info(
                f"Uploading GEDCOM to {upload_url}, "
                f"filename: {filename}, document_id: {document_id}"
            )
            
            # Prepare multipart form data
            files = {
                'file': (filename, gedcom_content.encode('utf-8'), 'text/gedcom')
            }
            
            # Send POST request
            with httpx.Client(timeout=self.upload_timeout) as client:
                response = client.post(
                    upload_url,
                    files=files,
                    headers=self._get_headers()
                )
                response.raise_for_status()
            
            # Parse response
            result = response.json()
            file_id = result.get('file_id')
            
            if not file_id:
                raise ValueError("Response did not contain file_id")
            
            logger.info(f"GEDCOM uploaded successfully. File ID: {file_id}")
            
            return {
                "success": True,
                "file_id": file_id,
                "filename": filename,
                "document_id": document_id,
                "response": result
            }
            
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            logger.error(f"HTTP error during GEDCOM upload: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "status_code": e.response.status_code
            }
        except httpx.RequestError as e:
            error_msg = f"Request error: {str(e)}"
            logger.error(f"Request error during GEDCOM upload: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Unexpected error during GEDCOM upload: {error_msg}", exc_info=True)
            return {
                "success": False,
                "error": error_msg
            }
    
    def trigger_parse(self, file_id: str) -> Dict[str, Any]:
        """
        Trigger parsing of an uploaded GEDCOM file.
        
        Args:
            file_id: ID of the uploaded file
        
        Returns:
            Dictionary containing parsing results and statistics
        
        Raises:
            Exception: If parsing trigger fails or is disabled
        """
        if not self.enabled:
            logger.warning("Application upload is disabled, skipping parse")
            return {
                "success": False,
                "skipped": True,
                "reason": "Application upload disabled"
            }
        
        try:
            parse_url = f"{self.app_url}/parse/{file_id}"
            logger.info(f"Triggering GEDCOM parse at {parse_url}")
            
            # Send POST request with longer timeout (parsing can take time)
            with httpx.Client(timeout=self.parse_timeout) as client:
                response = client.post(
                    parse_url,
                    headers=self._get_headers()
                )
                response.raise_for_status()
            
            # Parse response
            result = response.json()
            statistics = result.get('statistics', {})
            
            logger.info(f"GEDCOM parsing completed. Statistics: {statistics}")
            
            return {
                "success": True,
                "file_id": file_id,
                "statistics": statistics,
                "response": result
            }
            
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            logger.error(f"HTTP error during GEDCOM parse: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "status_code": e.response.status_code
            }
        except httpx.RequestError as e:
            error_msg = f"Request error: {str(e)}"
            logger.error(f"Request error during GEDCOM parse: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Unexpected error during GEDCOM parse: {error_msg}", exc_info=True)
            return {
                "success": False,
                "error": error_msg
            }
    
    def upload_and_parse(
        self,
        gedcom_content: str,
        filename: str,
        document_id: Optional[str] = None,
        auto_parse: bool = True
    ) -> Dict[str, Any]:
        """
        Upload GEDCOM and optionally trigger parsing in one operation.
        
        Args:
            gedcom_content: GEDCOM file content as string
            filename: Name of the GEDCOM file
            document_id: Optional document ID for tracking
            auto_parse: Whether to automatically trigger parsing after upload
        
        Returns:
            Dictionary with combined upload and parse results
        """
        # Upload GEDCOM
        upload_result = self.upload_gedcom(gedcom_content, filename, document_id)
        
        if not upload_result.get("success"):
            return upload_result
        
        # Optionally trigger parsing
        if auto_parse:
            file_id = upload_result.get("file_id")
            parse_result = self.trigger_parse(file_id)
            
            return {
                "success": parse_result.get("success", False),
                "upload": upload_result,
                "parse": parse_result
            }
        
        return upload_result
