#!/bin/bash

# Function to install Homebrew if not installed
install_homebrew() {
  echo "Homebrew not found. Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  export PATH="/opt/homebrew/bin:$PATH"
}

# Function to install Python using Homebrew
install_python() {
  echo "Installing Python3 using Homebrew..."
  brew install python
}

# Check if Python is installed
if ! command -v python3 &> /dev/null
then
  echo "Python3 not found."

  # Check if Homebrew is installed
  if ! command -v brew &> /dev/null
  then
    install_homebrew
  fi

  install_python
else
  echo "Python3 is already installed."
fi

# Change to project directory
cd "$(dirname "$0")/src"

# Check Python version
python3 -V

# Upgrade pip
python3 -m pip install --upgrade pip

# Create virtual environment if not exists
if [ ! -d "myenv" ]; then
    python3 -m venv myenv
fi

# Activate virtual environment
source myenv/bin/activate

# Install packages
pip install -r requirements.txt

echo "Current directory: $(pwd)"

# Run the app
python -m src.main
