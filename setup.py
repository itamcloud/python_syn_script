import os
import platform
import subprocess
import sys

def run(cmd, shell=False):
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=shell, check=True)
    return result

def main():
    # Check Python version
    run([sys.executable, "--version"])

    # Create virtual environment
    run([sys.executable, "-m", "venv", "myenv"])

    # Activate virtual environment and install requirements
    if platform.system() == "Windows":
        activate = ".\\myenv\\Scripts\\activate"
        pip = ".\\myenv\\Scripts\\pip"
        python_exec = ".\\myenv\\Scripts\\python"
    else:
        activate = "source ./myenv/bin/activate"
        pip = "./myenv/bin/pip"
        python_exec = "./myenv/bin/python"

    # Install requirements
    run([pip, "install", "-r", "requirements.txt"])

    # Run main script
    run([python_exec, "-m", "src.main"])

if __name__ == "__main__":
    main()