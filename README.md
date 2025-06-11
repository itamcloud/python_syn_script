# Linux/Windows/mac
# install the python on the system 3.12
# change the directory to src
```
python3 -V
```
## install the venv only in Linux, for windows and mac skip this step
```
pip install --upgrade pip
```
## Create a virtual environment
```
python3 -m venv myenv
```
## Activate the virtual environment
```
source myenv/bin/activate
```
## Install packages from requirements.txt
```
pip install -r requirements.txt
```
# run the main.py file
```
python -m src.main
```
