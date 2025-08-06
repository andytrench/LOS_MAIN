# Frequency Hardcoding Fix

## Issue Description

**Problem**: AI PDF processing was extracting correct frequency values (e.g., 18 GHz) from PDFs, but they were being overridden by hardcoded 11.0 GHz defaults in the validation pipeline.

**Example**: 
- PDF shows: `"Frequency (GHz) = 18.00 GHz"`
- AI correctly extracted: `"frequency_ghz": 18.0`
- Final result: `11.0 GHz` ❌ (overridden by hardcoded default)

## Root Cause

Multiple hardcoded `11.0 GHz` fallback values in the validation logic that were too aggressive:

1. **utilities/file_handler.py**: Lines 53, 54, 59, 60, 62, 63
2. **utilities/site_manager.py**: Lines 58, 59, 64, 65, 67, 68
3. **manual_sites.py**: Line 438
4. Various other files with 11.0 GHz function defaults

## Solution Applied

### 1. Fixed Validation Logic

**Before**:
```python
# If frequency extraction failed or user cancelled input
frequency_ghz = 11.0  # Hardcoded override!
```

**After**:
```python
# If user cancels, preserve original extracted value
frequency_ghz = data['general_parameters'].get('frequency_ghz')
if frequency_ghz is None:
    frequency_ghz = None  # Don't use hardcoded defaults
```

### 2. Improved Error Handling

**Before**: Silent override to 11.0 GHz
**After**: 
- Valid frequencies are preserved
- Invalid frequencies trigger user prompts
- No silent overrides with hardcoded values

### 3. Enhanced AI Prompt

Updated `utilities/ai_processor.py` to be more explicit:
```
CRITICAL: 
- Extract the EXACT frequency value from the document (e.g., if it says "18.00 GHz", extract 18.0)
- If you cannot find the frequency in the document, set frequency_ghz to null
- Do NOT use 0.0, 11.0, or any default/assumed values
- Common frequencies include: 6, 11, 18, 23, 38 GHz - extract whatever is actually stated
```

### 4. Respects User Preference

The fix ensures that frequency values are read from `tower_parameters.json` as preferred by the user, rather than using arbitrary hardcoded values.

## Files Modified

1. **utilities/file_handler.py**
   - Removed hardcoded 11.0 GHz defaults
   - Preserves correctly extracted frequencies
   - Better error handling for invalid inputs

2. **utilities/site_manager.py**
   - Removed hardcoded 11.0 GHz defaults
   - Preserves correctly extracted frequencies
   - Better error handling for invalid inputs

3. **utilities/ai_processor.py**
   - Enhanced AI prompt for more accurate frequency extraction
   - Explicit instructions against using default values

4. **manual_sites.py**
   - Updated to read from tower_parameters.json first
   - 11.0 GHz only as final fallback for manual input form

5. **test_scripts/test_frequency_extraction.py**
   - New comprehensive test to verify the fix works
   - Tests various frequency values (6, 11, 18, 23 GHz)
   - Validates that extracted frequencies are preserved

## Test Results

✅ **18 GHz Link**: Correctly preserved (was being overridden to 11 GHz)
✅ **6 GHz Link**: Correctly preserved  
✅ **23 GHz Link**: Correctly preserved
✅ **Invalid Frequencies**: Properly detected and prompt user
✅ **Real AI Example**: 18.0 GHz from PDF now preserved correctly

## Impact

### Before Fix:
- ❌ Valid frequencies overridden by 11.0 GHz defaults
- ❌ AI extraction wasted (correct values discarded)
- ❌ Inaccurate frequency data in reports
- ❌ User reports showing wrong frequencies

### After Fix:
- ✅ AI-extracted frequencies preserved correctly
- ✅ 18 GHz, 6 GHz, 23 GHz, etc. all work properly
- ✅ Respects user preference for tower_parameters.json
- ✅ No more silent overrides with hardcoded values
- ✅ Accurate frequency data in all reports

## Usage Notes

1. **For AI PDF Processing**: Frequencies will be extracted exactly as stated in the PDF
2. **For Manual Input**: tower_parameters.json is checked first, 11.0 GHz as final fallback only
3. **Error Handling**: Invalid frequencies prompt user input rather than silent defaults
4. **Validation**: Only truly invalid values (null, 0, negative) trigger prompts

## Verification

Run the test script to verify the fix:
```bash
python test_scripts/test_frequency_extraction.py
```

This ensures that:
- Valid frequencies are preserved
- Invalid frequencies are properly handled
- No hardcoded overrides occur
- User preferences are respected 