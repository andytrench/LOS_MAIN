#!/usr/bin/env python3
import os
import sys

# Path to the ee main.py file
ee_main_path = os.path.join(os.path.expanduser("~"), "miniconda3", "envs", "gdal_env", "lib", "python3.10", "site-packages", "ee", "main.py")

# Read the file
with open(ee_main_path, 'r') as f:
    content = f.read()

# Replace StringIO with io.StringIO
content = content.replace('import StringIO', 'import io')
content = content.replace('StringIO.StringIO', 'io.StringIO')

# Write the file back
with open(ee_main_path, 'w') as f:
    f.write(content)

print("Fixed StringIO import in Earth Engine module")
