# PDF Text Extraction Tools

This package contains two tools to help you analyze how text is extracted from PDF files:

1. `pdf_text_extractor.py` - A simple tool to extract raw text from PDFs
2. `pdf_analyzer.py` - A more advanced tool that provides detailed analysis of PDF structure and content

## Requirements

These tools require Python 3.6+ and the PyMuPDF library:

```bash
pip install PyMuPDF
```

## Simple Text Extractor

The `pdf_text_extractor.py` script extracts all text from a PDF and saves it to a text file.

### Usage

```bash
python pdf_text_extractor.py path/to/your/file.pdf [options]
```

### Options

- `-o, --output-dir DIR` - Directory to save the output (default: same directory as PDF)
- `-p, --page-limit NUM` - Maximum number of pages to extract (default: all pages)
- `-v, --verbose` - Print detailed information during extraction

### Example

```bash
python pdf_text_extractor.py microwave_link.pdf -v
```

This will extract all text from `microwave_link.pdf`, save it to a text file, and print detailed information during the process.

## Advanced PDF Analyzer

The `pdf_analyzer.py` script provides more detailed analysis of PDF structure and content.

### Usage

```bash
python pdf_analyzer.py path/to/your/file.pdf [options]
```

### Options

- `-o, --output-dir DIR` - Directory to save the output files (default: same directory as PDF)
- `-p, --page-limit NUM` - Maximum number of pages to analyze (default: all pages)
- `-v, --verbose` - Print detailed information during analysis
- `--no-tables` - Skip table extraction

### Example

```bash
python pdf_analyzer.py microwave_link.pdf -v
```

This will analyze `microwave_link.pdf` and generate three output files:
1. A raw text file containing all extracted text
2. A JSON file with detailed analysis results
3. A human-readable report with key findings

## Understanding the Output

### Text Extractor Output

The text extractor creates a single text file with:
- A header with information about the extraction
- The full extracted text
- Text separated by page

### PDF Analyzer Output

The PDF analyzer creates three files:

1. **Raw Text File** - Contains all extracted text from the PDF
2. **JSON Analysis File** - Contains detailed analysis results in JSON format:
   - PDF metadata
   - Page information (dimensions, block count, etc.)
   - Potential data fields (key-value pairs)
   - Potential coordinates (latitude/longitude)
3. **Human-Readable Report** - Contains:
   - PDF metadata
   - Page summary
   - Potential data fields
   - Potential coordinates
   - Full extracted text

## How This Helps with AI Processing

By examining the raw text extraction, you can:

1. See exactly what text PyMuPDF extracts from your PDFs
2. Understand how formatting is preserved or lost during extraction
3. Identify patterns that Claude might use to extract structured data
4. Troubleshoot issues where Claude misinterprets or misses information

This can help you improve the prompts used with Claude or modify your PDF processing pipeline to better handle different PDF formats.
