pip3 -qq install pylint flake8 pytest

echo "Running pylint"
cd ../doper
pylint $(find . -name "*.py" -not -path "*/interface/*")

echo "Running pytest"
pytest