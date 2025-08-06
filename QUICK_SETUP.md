# 🚀 LOS_MAIN Quick Setup Guide

Get up and running with the LOS Tool in minutes!

## Choose Your Platform

### 📱 macOS (Recommended for M1/M2 Macs)
```bash
git clone https://github.com/andytrench/LOS_MAIN.git
cd LOS_MAIN
chmod +x install_macos.sh
./install_macos.sh
```
**Time: ~10-15 minutes**

### 🪟 Windows
1. **Download**: Clone or download this repository
2. **Run**: Right-click `install_windows.bat` → "Run as Administrator"  
3. **Wait**: Installation takes 15-20 minutes
4. **Launch**: Double-click the "LOS Tool" desktop shortcut

### 🐧 Linux (Ubuntu/Debian/Fedora/CentOS)
```bash
git clone https://github.com/andytrench/LOS_MAIN.git
cd LOS_MAIN
chmod +x install_linux.sh
./install_linux.sh
```
**Time: ~10-15 minutes**

## What Gets Installed

### System Dependencies
- ✅ **Python 3.11** (via Miniconda)
- ✅ **GDAL** (Geospatial Data Abstraction Library)
- ✅ **PostgreSQL + PostGIS** (Spatial database)
- ✅ **Tesseract OCR** (Document text extraction)

### Python Environment
- ✅ **Conda environment** named `lostool`
- ✅ **40+ Python packages** including:
  - Geospatial: `geopandas`, `rasterio`, `shapely`
  - AI/ML: `anthropic`, `earthengine-api`
  - GUI: `tkinter`, `matplotlib`
  - Data: `pandas`, `numpy`, `scipy`

### Application Setup
- ✅ **Desktop shortcut** (Windows/Linux)
- ✅ **Command launcher** (macOS)
- ✅ **Database configured** with spatial extensions
- ✅ **Environment template** for your API keys

## After Installation

### 1. Configure Your API Keys
```bash
# Copy the template
cp .env.template .env

# Edit with your credentials
nano .env  # or use any text editor
```

**Required API Keys:**
- **Anthropic** (for AI document processing)
- **Google Maps** (for mapping features)
- **AWS** (for LiDAR data access)
- **Google Earth Engine** (for satellite imagery)

### 2. Add Google Earth Engine Credentials
1. Download your GEE service account JSON file
2. Place it in the LOS_MAIN directory
3. Update the path in your `.env` file

### 3. Run the Application

**macOS:**
```bash
source activate_lostool.sh
python dropmap.py
```
*Or double-click `LOS_Tool.command` on your Desktop*

**Windows:**
- Double-click "LOS Tool" desktop shortcut
- Or run `Run_LOS_Tool.bat`

**Linux:**
```bash
source activate_lostool.sh
python dropmap.py
```
*Or find "LOS Tool" in your applications menu*

## Troubleshooting

### Installation Issues

**"Permission denied" on macOS/Linux:**
```bash
chmod +x install_*.sh
sudo ./install_*.sh
```

**Windows installer fails:**
- Run as Administrator
- Disable antivirus temporarily
- Check Windows version (requires Windows 10+)

**GDAL issues on Apple Silicon:**
The installer automatically handles this, but if you have issues:
```bash
conda install -c conda-forge gdal
```

### Runtime Issues

**Application won't start:**
1. Check that conda environment is activated
2. Verify all API keys are configured
3. Ensure PostgreSQL service is running

**Database connection errors:**
```bash
# Check PostgreSQL status
brew services list | grep postgresql  # macOS
sudo systemctl status postgresql      # Linux
net start postgresql*                 # Windows
```

**Missing GUI on Linux:**
```bash
# Install desktop packages
sudo apt-get install python3-tk
pip install tkinterdnd2 tkintermapview
```

## Getting Help

- 📧 **Email**: andytrench@gmail.com
- 🐛 **Issues**: GitHub Issues page
- 📖 **Docs**: Check the `docs/` folder for detailed guides

---

## Pro Tips

### Performance Optimization
- Use SSD storage for LiDAR data processing
- Ensure 8GB+ RAM for large datasets
- Enable GPU acceleration if available

### Development Setup
```bash
# For developers who want to modify the code
conda activate lostool
pip install pytest pytest-cov  # Testing tools
```

### Backup Your Configuration
```bash
# Backup your API keys and settings
cp .env .env.backup
tar -czf lostool_config.tar.gz .env tower_parameters.json
```

---

**Total Setup Time: 15-20 minutes**  
**Disk Space Required: ~2-3 GB**  
**Memory Requirements: 4GB+ RAM (8GB recommended)**