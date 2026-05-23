# Image Resize Fix for Datalab SDK Width Constraint

## Problem
The Datalab SDK has a maximum image dimension constraint of **4800x4800 pixels**. When processing an image with dimensions exceeding this limit (e.g., 5092px wide), the SDK returns:
```
ConversionResult(success=False, error='Input width 5092 exceeds maximum width of 4800 pixels.')
```

## Solution Implemented
Automatic image resizing that:
1. **Detects oversized images** before sending to Datalab SDK
2. **Scales down intelligently** while maintaining aspect ratio
3. **Uses high-quality resampling** (LANCZOS) to preserve OCR accuracy
4. **Cleans up temporary files** automatically
5. **Logs comprehensive diagnostics** for monitoring

## Implementation Details

### New Method: `_resize_if_needed()`
Located in [`ocr_processor.py`](src/services/ocr_processor.py:46-113)

**Key Features:**
- Checks image dimensions using PIL/Pillow
- Calculates optimal scale factor: `min(4800/width, 4800/height)`
- For 5092x3508 image: scale factor = 0.9427, resulting in 4800x3306
- Preserves image format (JPEG, PNG, etc.)
- Maintains high quality (JPEG quality=95, LANCZOS resampling)
- Returns tuple: `(path_to_use, was_resized)`

### Updated: `process_image()`
Located in [`ocr_processor.py`](src/services/ocr_processor.py:115-195)

**Workflow:**
1. Call [`_resize_if_needed()`](src/services/ocr_processor.py:137) to get processing path
2. Process with Datalab SDK using resized image if needed
3. Extract results (preserves all existing functionality)
4. Clean up temporary file in `finally` block

### Example Log Output
```
INFO: Original image dimensions: 5092x3508 pixels
INFO: Resizing image from 5092x3508 to 4800x3306 (scale factor: 0.9427)
INFO: Resized image saved to temporary file: /tmp/ocr_resized_xyz.jpg
INFO: Calling Datalab SDK with options: format=markdown, mode=accurate, paginate=True
INFO: Datalab SDK returned result type: <class 'ConversionResult'>
INFO: Conversion success status: True
INFO: OCR processing completed - Output length: 1234 chars
INFO: Cleaned up temporary file: /tmp/ocr_resized_xyz.jpg
```

## Technical Specifications

### Constraints
- **Maximum Width**: 4800 pixels
- **Maximum Height**: 4800 pixels
- **Resampling Algorithm**: LANCZOS (highest quality)
- **JPEG Quality**: 95 (near-lossless)

### Dependencies Added
- `Pillow>=10.0.0` in [`requirements.txt`](requirements.txt)

### Behavior
| Original Size | New Size | Scale Factor | Action |
|--------------|----------|--------------|---------|
| 5092x3508    | 4800x3306 | 0.9427       | Resized |
| 4000x3000    | 4000x3000 | 1.0000       | No change |
| 6000x6000    | 4800x4800 | 0.8000       | Resized |
| 7200x2400    | 4800x1600 | 0.6667       | Resized |

## Benefits

### 1. **Automatic Handling**
No manual intervention required for oversized images

### 2. **Quality Preservation**
- LANCZOS resampling (better than bicubic/bilinear)
- High JPEG quality settings
- Original format preservation

### 3. **OCR Accuracy**
- Text remains readable at 4800px width
- Aspect ratio maintained (no distortion)
- High-quality downsampling enhances OCR

### 4. **Resource Management**
- Temporary files automatically cleaned up
- Memory-efficient streaming approach
- Graceful fallback on resize failure

### 5. **Observability**
- Detailed logging at each step
- Dimension tracking
- Scale factor reporting
- Error diagnostics

## Testing Recommendations

### Unit Tests
```python
def test_resize_5092px_image():
    """Test that 5092px wide image is resized to 4800px"""
    processor = OCRProcessor()
    path, was_resized = processor._resize_if_needed("test_5092.jpg")
    
    assert was_resized == True
    
    with Image.open(path) as img:
        assert img.width == 4800
        assert img.height == 3306  # Aspect ratio preserved

def test_no_resize_within_limits():
    """Test that images within limits are not resized"""
    processor = OCRProcessor()
    path, was_resized = processor._resize_if_needed("test_4000.jpg")
    
    assert was_resized == False
```

### Integration Tests
1. Process actual 5092px image through pipeline
2. Verify successful OCR completion
3. Validate markdown output quality
4. Check temporary file cleanup

## Deployment

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Restart Service
```bash
docker-compose down
docker-compose up --build
```

### 3. Monitor Logs
Watch for resize operations:
```bash
docker-compose logs -f | grep -i "resizing"
```

## Troubleshooting

### Issue: Low OCR Quality After Resize
**Solution**: Increase JPEG quality or adjust resampling algorithm

### Issue: Memory Usage High
**Solution**: Process images sequentially, ensure cleanup works

### Issue: Temporary Files Not Cleaned
**Solution**: Check `finally` block execution, verify permissions on `/tmp`

## Future Enhancements

### Optional Improvements
1. **Configurable limits** via environment variables
2. **Image splitting** for extremely large images (>10000px)
3. **Smart cropping** to preserve important regions
4. **Pre-processing** (deskewing, contrast enhancement)
5. **Parallel tile processing** for massive documents

### Configuration Example
```python
# In config.py
MAX_IMAGE_WIDTH = int(os.getenv("MAX_IMAGE_WIDTH", "4800"))
MAX_IMAGE_HEIGHT = int(os.getenv("MAX_IMAGE_HEIGHT", "4800"))
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "95"))
```
