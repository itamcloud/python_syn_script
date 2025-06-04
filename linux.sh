#!/bin/bash

# Check Python version
python3 --version

# Create virtual environment
python3 -m venv myenv

# Activate virtual environment
source myenv/bin/activate

# Install requirements
pip install -r requirements.txt

# Run the main script
python -m src.main