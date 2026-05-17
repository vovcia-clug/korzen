"""GEDCOM uploader for hosted application integration."""
import httpx
from typing import Optional, Dict, Any
from ..utils.logger import get_logger

logger = get_logger(__name__)


class GedcomUploader:
    """Upload and parse GEDCOM files on the hosted application."""
    
    def __init__(self, app_url: str, api_key: Optional[str] = None):
        """
        Initialize GEDCOM uploader.
        
        Args:
            app_url: Base URL of the hosted application (e.g., https://korzen.vovcia.net)
            api_key: Optional API key for authentication
        """
        self.app_url = app_url.rstrip('/')
        self.api_key = api_key
        logger.info(f"GedcomUploader initialized with app_url: {self.app_url}")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for requests."""
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    def upload_gedcom(self, gedcom_content: str, filename: str) -> str:
        """
        Upload GEDCOM file to the hosted application.
        
        Args:
            gedcom_content: GEDCOM file content as string
            filename: Name of the GEDCOM file
        
        Returns:
            file_id from the response
        
        Raises:
            Exception: If upload fails
        """
        try:
            upload_url = f"{self.app_url}/upload"
            logger.info(f"Uploading GEDCOM to {upload_url}, filename: {filename}")
            
            # Prepare multipart form data
            files = {
                'file': (filename, gedcom_content.encode('utf-8'), 'text/gedcom')
            }
            
            # Send POST request with 30s timeout
            with httpx.Client(timeout=30.0) as client:
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
            return file_id
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during GEDCOM upload: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Failed to upload GEDCOM: HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"Request error during GEDCOM upload: {e}")
            raise Exception(f"Failed to upload GEDCOM: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error during GEDCOM upload: {e}", exc_info=True)
            raise
    
    def trigger_parse(self, file_id: str) -> Dict[str, Any]:
        """
        Trigger parsing of an uploaded GEDCOM file.
        
        Args:
            file_id: ID of the uploaded file
        
        Returns:
            Dictionary containing parsing statistics
        
        Raises:
            Exception: If parsing trigger fails
        """
        try:
            parse_url = f"{self.app_url}/parse/{file_id}"
            logger.info(f"Triggering GEDCOM parse at {parse_url}")
            
            # Send POST request with 300s timeout (parsing can take time)
            with httpx.Client(timeout=300.0) as client:
                response = client.post(
                    parse_url,
                    headers=self._get_headers()
                )
                response.raise_for_status()
            
            # Parse response
            result = response.json()
            statistics = result.get('statistics', {})
            
            logger.info(f"GEDCOM parsing completed. Statistics: {statistics}")
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during GEDCOM parse: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Failed to parse GEDCOM: HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"Request error during GEDCOM parse: {e}")
            raise Exception(f"Failed to parse GEDCOM: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error during GEDCOM parse: {e}", exc_info=True)
            raise
