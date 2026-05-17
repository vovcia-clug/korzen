# AGE Graph Import Progress Tracking

## Overview

Comprehensive progress tracking has been added to the AGE (Apache Graph Extension) graph import functionality. This provides detailed logging and metrics during potentially long import operations, making it easy to monitor what's happening and identify any issues.

## Features Added

### 1. ImportProgress Class

A new `ImportProgress` class in [`src/app/services/age_graph_importer.py`](src/app/services/age_graph_importer.py) tracks:

- **Vertices Created/Skipped by Type**:
  - Person vertices
  - Event vertices (baptisms, deaths)
  - Source vertices

- **Edges Created/Skipped by Type**:
  - PARENT_OF (parent-child relationships)
  - MARRIED_TO (marriage relationships)
  - BAPTIZED_IN (person to baptism event)
  - DIED_IN (person to death event)
  - GODPARENT_OF (godparent relationships)
  - FROM_SOURCE (entity to source)

- **Timing Information**:
  - Elapsed time in human-readable format (seconds, minutes, hours)
  - Automatic tracking from start to finish

- **Error and Warning Tracking**:
  - All errors are logged and counted
  - Warnings are tracked separately
  - Full error messages preserved for debugging

### 2. Enhanced Progress Logging

The import process now logs detailed progress information at multiple levels:

#### Initialization Phase
```
================================================================================
STARTING AGE GRAPH IMPORT
================================================================================
Records to import:
  - Persons: 150
  - Baptism events: 120
  - Death events: 98
  - Marriage relationships: 45
  - Parent-child relationships: 280
Total entities: 413

Creating source vertex...
✓ Source vertex created for batch abc-123
```

#### Import Progress for Each Entity Type
```
Importing 150 person vertices...
  Progress: 15/150 persons (10.0%) - Elapsed: 2.3s
  Progress: 30/150 persons (20.0%) - Elapsed: 4.1s
  ...
  Progress: 150/150 persons (100.0%) - Elapsed: 18.5s
✓ Completed person import: 148 created, 2 skipped
  Time elapsed: 18.5s
```

#### Percentage Completion
Progress is logged at:
- Every 10% of completion
- Every 50-100 records (depending on entity type)
- This ensures regular updates without flooding logs

#### Final Summary
```
================================================================================
AGE GRAPH IMPORT SUMMARY
================================================================================
Total time: 1.2m
Vertices created: 368
  - Person: 148
  - Event: 218
  - Source: 1
Vertices skipped (already exist): 2
Edges created: 845
  - PARENT_OF: 276
  - MARRIED_TO: 90
  - BAPTIZED_IN: 120
  - DIED_IN: 98
  - FROM_SOURCE: 369
Edges skipped (already exist): 12
Errors encountered: 0
Warnings encountered: 0
================================================================================

Current AGE graph statistics:
  - Total persons in graph: 1,245
  - Total events in graph: 1,018
  - Total sources in graph: 5
  - Total parent-child relationships: 2,104
  - Total marriage relationships: 456
```

### 3. Automatic Progress Tracking in Methods

Each vertex/edge creation method in [`AgeGraphImporter`](src/app/services/age_graph_importer.py) now automatically:

- Increments counters when entities are created
- Tracks skips when entities already exist
- Logs errors with full context
- Updates the progress object in real-time

### 4. Integration with GEDCOM Parser

The [`GedcomParser`](src/app/gedcom_parser.py) `_import_to_age_graph()` method now:

- Calculates total counts upfront to show expected workload
- Provides phase-by-phase progress updates
- Shows percentage completion for each entity type
- Includes timing information with each update
- Logs comprehensive summary at completion

## How It Works

### During Import

1. **Pre-scan**: Queries database to count all records that will be imported
2. **Progress Calculation**: Determines total workload and milestone intervals
3. **Incremental Updates**: Logs progress at regular intervals (10% or fixed record counts)
4. **Real-time Tracking**: Updates counters as each entity is processed
5. **Error Handling**: Captures and logs any errors without stopping the process

### Logging Levels

The system uses appropriate logging levels:

- **INFO**: Main progress milestones, completion messages, summaries
- **DEBUG**: Individual vertex/edge creation (when enabled)
- **ERROR**: Any errors encountered during import
- **WARNING**: Warnings about data issues or potential problems

### Performance Considerations

- Progress logging is configured to avoid excessive output
- Large imports log every 10% completion to balance visibility and log volume
- Smaller imports log more frequently (every 50-100 records)
- Debug logging can be disabled for production to improve performance

## Usage Example

When you parse a GEDCOM file, you'll automatically see progress information:

```python
# In your application
parser = GedcomParser('genealogy_data.ged', file_id)
stats = parser.parse_and_import()

# Progress is automatically logged to the configured logger
# stats dictionary now includes:
# - age_import: ImportProgress summary
# - age_graph_stats: Current graph statistics
```

## Viewing Progress

### In Console/Logs

When running the application, progress appears in standard logs:

```bash
# Run your Flask application
python src/main.py

# Or check logs if running with logging configured
tail -f logs/korzen.log
```

### In Application

The progress information is logged using Python's `logging` module with the logger name from the module (`src.app.services.age_graph_importer` and `src.app.gedcom_parser`).

Configure logging in your [`src/app/config.py`](src/app/config.py) or environment to control verbosity:

```python
import logging

# For detailed progress (development)
logging.basicConfig(level=logging.INFO)

# For minimal output (production)
logging.basicConfig(level=logging.WARNING)

# For full debugging
logging.basicConfig(level=logging.DEBUG)
```

## Benefits

1. **Visibility**: Know exactly what's happening during long imports
2. **Progress Estimation**: See percentage completion and elapsed time
3. **Error Detection**: Immediately identify if/when errors occur
4. **Performance Monitoring**: Track how long each phase takes
5. **Debugging**: Detailed logs help troubleshoot issues
6. **Confidence**: Clear feedback that the import is progressing normally

## Statistics Available

After import, you can access:

```python
stats = parser.parse_and_import()

# Import progress summary
import_summary = stats['age_import']
print(f"Total time: {import_summary['elapsed_time']}")
print(f"Vertices created: {import_summary['vertices']['total_created']}")
print(f"Edges created: {import_summary['edges']['total_created']}")

# Current graph statistics
graph_stats = stats['age_graph_stats']
print(f"Total persons: {graph_stats['persons']}")
print(f"Total parent relationships: {graph_stats['parent_of_edges']}")
```

## Future Enhancements

Possible improvements for the future:

1. **Web UI Progress Bar**: Show real-time progress in the web interface
2. **Estimated Time Remaining**: Calculate ETA based on current progress
3. **Detailed Error Report**: Generate error report file for large imports
4. **Progress API Endpoint**: REST API to query import progress
5. **Email Notifications**: Send notification when large imports complete
6. **Progress Persistence**: Save progress to database for interrupted imports

## Technical Details

### Classes and Methods Modified

1. **`ImportProgress`** class (new)
   - Tracks all progress metrics
   - Methods: `elapsed_time()`, `get_summary()`, `log_summary()`

2. **`AgeGraphImporter`** class (modified)
   - Added `self.progress` attribute
   - Updated all vertex/edge creation methods to track progress
   - Methods track created/skipped counts and errors

3. **`GedcomParser._import_to_age_graph()`** (modified)
   - Pre-scans records to calculate totals
   - Logs progress at regular intervals
   - Generates comprehensive summary

### Dependencies

No new dependencies required. Uses only:
- Python standard library `time` module
- Existing `logging` module
- Existing `datetime` module

## Conclusion

The AGE graph import process now provides comprehensive progress tracking, making it easy to monitor imports of any size and quickly identify any issues that occur during the process.
