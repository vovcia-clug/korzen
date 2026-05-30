"""S3 handler for uploading GEDCOM files."""
import os
from pathlib import Path
from typing import Optional
import aioboto3
from botocore.exceptions import ClientError

from ..utils.logger import get_logger

logger = get_logger(__name__)


class S3Handler:
    """Handle S3 upload operations for GEDCOM files."""
    
    def __init__(
        self,
        aws_config: dict,
        output_bucket: str,
        output_prefix: str = "gedcom-files/"
    ):
        """
        Initialize S3 handler.
        
        Args:
            aws_config: AWS configuration dictionary for boto3
            output_bucket: S3 bucket name for output GEDCOM files
            output_prefix: Prefix for output files in S3
        """
        self.output_bucket = output_bucket
        self.output_prefix = output_prefix
        self.aws_config = aws_config
        
        # Create aioboto3 session (client opened lazily inside each async method)
        self.session = aioboto3.Session()
        
        logger.info(
            f"S3Handler initialized - Output: {output_bucket}/{output_prefix}"
        )
    
    async def upload_gedcom(
        self,
        content: str,
        document_id: str,
        filename: Optional[str] = None,
        source_s3_uri: Optional[str] = None,
        preserve_structure: bool = True
    ) -> str:
        """
        Upload GEDCOM content to S3.
        
        Args:
            content: GEDCOM file content as string
            document_id: Document identifier for organizing files
            filename: Optional custom filename (defaults to document_id.ged)
            source_s3_uri: Optional source image S3 URI to preserve directory structure
            preserve_structure: If True and source_s3_uri provided, preserve directory structure
        
        Returns:
            S3 URI of uploaded GEDCOM file
        
        Raises:
            ClientError: If S3 upload fails
        """
        # Generate output S3 key
        if filename is None:
            filename = f"{document_id}.ged"
        
        # Preserve directory structure if source URI is provided
        if preserve_structure and source_s3_uri:
            try:
                # Parse source S3 URI to extract the path structure
                # Format: s3://bucket/path/to/file.ext
                if source_s3_uri.startswith("s3://"):
                    # Remove s3://bucket/ prefix
                    path_part = source_s3_uri.split("/", 3)
                    if len(path_part) >= 4:
                        # Get the directory path (everything except the filename)
                        source_key = path_part[3]
                        source_path = Path(source_key)
                        parent_path = source_path.parent
                        
                        # Construct output key with preserved structure
                        if str(parent_path) != '.':
                            output_key = f"{self.output_prefix}{parent_path}/{filename}"
                        else:
                            output_key = f"{self.output_prefix}{filename}"
                        
                        logger.info(
                            f"Preserving directory structure from {source_s3_uri}: "
                            f"parent_path={parent_path}, output_key={output_key}"
                        )
                    else:
                        # Fallback to simple prefix if parsing fails
                        output_key = f"{self.output_prefix}{filename}"
                        logger.warning(
                            f"Could not parse source URI structure, using simple prefix: {source_s3_uri}"
                        )
                else:
                    # Fallback for non-s3:// URIs
                    output_key = f"{self.output_prefix}{filename}"
                    logger.warning(
                        f"Source URI not in s3:// format, using simple prefix: {source_s3_uri}"
                    )
            except Exception as e:
                # Fallback to simple prefix on any error
                output_key = f"{self.output_prefix}{filename}"
                logger.warning(
                    f"Error parsing source URI structure, using simple prefix: {e}"
                )
        else:
            # Original behavior: just use prefix + filename
            output_key = f"{self.output_prefix}{filename}"
        
        try:
            logger.info(
                f"Uploading GEDCOM ({len(content)} bytes) to "
                f"s3://{self.output_bucket}/{output_key}"
            )
            
            # Upload string content directly
            async with self.session.client("s3", **self.aws_config) as client:
                await client.put_object(
                    Bucket=self.output_bucket,
                    Key=output_key,
                    Body=content.encode('utf-8'),
                    ContentType='text/x-gedcom'
                )
            
            s3_uri = f"s3://{self.output_bucket}/{output_key}"
            logger.info(f"Successfully uploaded GEDCOM to {s3_uri}")
            return s3_uri
            
        except ClientError as e:
            logger.error(f"Failed to upload GEDCOM: {e}")
            raise
    
    async def upload_content(
        self,
        content: str,
        s3_key: str,
        content_type: str = "text/plain"
    ) -> str:
        """
        Upload arbitrary content to S3.
        
        Args:
            content: Content to upload as string
            s3_key: Full S3 key (including prefix)
            content_type: MIME type of the content
        
        Returns:
            S3 URI of uploaded file
        
        Raises:
            ClientError: If S3 upload fails
        """
        try:
            logger.info(
                f"Uploading content ({len(content)} bytes) to "
                f"s3://{self.output_bucket}/{s3_key}"
            )
            
            async with self.session.client("s3", **self.aws_config) as client:
                await client.put_object(
                    Bucket=self.output_bucket,
                    Key=s3_key,
                    Body=content.encode('utf-8'),
                    ContentType=content_type
                )
            
            s3_uri = f"s3://{self.output_bucket}/{s3_key}"
            logger.info(f"Successfully uploaded content to {s3_uri}")
            return s3_uri
            
        except ClientError as e:
            logger.error(f"Failed to upload content: {e}")
            raise
