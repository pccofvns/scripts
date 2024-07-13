#!/bin/sh

if python -c 'import platform; major = platform.python_version_tuple(); print(major)'; then
	echo "python is installed .............."
	python_executable='python'
elif python3 -c 'import platform; major = platform.python_version_tuple()'; then
	echo "python3 is installed .............."
	python_executable='python3'
fi

ver=$($python_executable -V 2>&1 | sed 's/.* \([0-9]\).\([0-9]\).*/\1\2/')
if [ "$ver" -lt "30" ]; then
    echo "This script requires python 3.0 or greater"
    exit 1
else 
	echo "Python version is > 3 ..."
fi

$python_executable -m venv .venv
source .venv/bin/activate
echo $python_executable -m pip -V
echo `$python_executable -m pip -V`
echo $python_executable -m pip install -r requirements.txt
$python_executable -m pip install -r requirements.txt
deactivate
