# Tesseract OCR Installation Guide

This guide explains how to install Tesseract OCR, which is required for the OCR-based PDF text extraction in our application.

## macOS Installation

### Using Homebrew (Recommended)

1. Install Homebrew if you don't have it already:
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. Install Tesseract OCR:
   ```bash
   brew install tesseract
   ```

3. Verify the installation:
   ```bash
   tesseract --version
   ```

### Using MacPorts

1. Install MacPorts if you don't have it already (from https://www.macports.org/install.php)

2. Install Tesseract OCR:
   ```bash
   sudo port install tesseract
   ```

## Windows Installation

1. Download the installer from the UB Mannheim project:
   https://github.com/UB-Mannheim/tesseract/wiki

2. Run the installer and follow the instructions.
   - Make sure to note the installation path (default is `C:\Program Files\Tesseract-OCR`)
   - Select additional languages during installation if needed

3. Add Tesseract to your PATH:
   - Right-click on "This PC" or "My Computer" and select "Properties"
   - Click on "Advanced system settings"
   - Click on "Environment Variables"
   - Under "System variables", find and select "Path", then click "Edit"
   - Click "New" and add the Tesseract installation path (e.g., `C:\Program Files\Tesseract-OCR`)
   - Click "OK" on all dialogs to save

4. Verify the installation by opening a new Command Prompt and typing:
   ```
   tesseract --version
   ```

## Linux Installation

### Ubuntu/Debian

```bash
sudo apt update
sudo apt install tesseract-ocr
```

### Fedora

```bash
sudo dnf install tesseract
```

### CentOS/RHEL

```bash
sudo yum install tesseract
```

## Python Package Installation

After installing Tesseract OCR, install the Python package:

```bash
pip install pytesseract pillow
```

## Configuring the Application

If Tesseract is not in your system PATH, you'll need to specify its location in the code.

Open `utilities/ocr_processor.py` and uncomment the following line:

```python
# pytesseract.pytesseract.tesseract_cmd = r'/usr/local/bin/tesseract'  # macOS with Homebrew
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Windows
```

Update the path to match your Tesseract installation location.

## Testing the Installation

Run the comparison script to test if OCR is working correctly:

```bash
python compare_extraction_methods.py "path/to/your/pdf/file.pdf"
```

This will compare PyMuPDF and OCR-based extraction methods and show which one works better for your PDF files.

## Troubleshooting

### Common Issues

1. **"tesseract is not recognized as an internal or external command"**
   - Make sure Tesseract is in your PATH
   - Try specifying the full path in the code as shown above

2. **"TesseractNotFoundError: tesseract is not installed or it's not in your PATH"**
   - Set the path explicitly in the code:
     ```python
     pytesseract.pytesseract.tesseract_cmd = r'/path/to/tesseract'
     ```

3. **Poor OCR Quality**
   - Try increasing the DPI value in the code (e.g., from 300 to 400)
   - Adjust the preprocessing parameters in the `preprocess_image` function

4. **Slow Performance**
   - Reduce the DPI value (e.g., from 300 to 200) for faster processing at the cost of some accuracy
   - Limit OCR to only the first few pages if you know the relevant information is there
