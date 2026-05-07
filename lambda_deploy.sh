#!/bin/bash
# Package all Python files and dependencies into a Lambda deployment zip.
# Usage: bash lambda_deploy.sh
# Then upload lambda_package.zip to AWS Lambda console.
set -e

echo "🧹 Cleaning previous build..."
rm -rf dist
mkdir dist

echo "📦 Installing dependencies..."
pip install -r requirements.txt -t dist/ --quiet

echo "📋 Copying source files..."
cp *.py dist/

echo "🗜  Creating zip..."
cd dist && zip -r ../lambda_package.zip . -x "*.pyc" -x "__pycache__/*" && cd ..

SIZE=$(du -sh lambda_package.zip | cut -f1)
echo "✅ lambda_package.zip ready ($SIZE) — upload to AWS Lambda console"
echo ""
echo "Lambda settings:"
echo "  Handler:  rest_api.handler"
echo "  Runtime:  Python 3.11"
echo "  Timeout:  300 seconds"
echo "  Memory:   512 MB"