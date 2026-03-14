#!/bin/bash

echo "================================================"
echo "  Receipt Categorization - Git Setup"
echo "================================================"
echo ""

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "❌ Git is not installed!"
    echo "Install Git first, then run this script again."
    exit 1
fi

echo "✅ Git is installed"
echo ""

# Initialize Git if not already done
if [ ! -d ".git" ]; then
    echo "📁 Initializing Git repository..."
    git init
    echo "✅ Git initialized"
else
    echo "✅ Git already initialized"
fi

echo ""

# Configure Git
echo "⚙️  Configuring Git..."
echo "Enter your name (e.g., John Doe):"
read git_name
echo "Enter your email (e.g., john@example.com):"
read git_email

git config --global user.name "$git_name"
git config --global user.email "$git_email"

echo "✅ Git configured"
echo ""

# Add all files
echo "📦 Adding files..."
git add .
echo "✅ Files added"
echo ""

# Create commit
echo "💾 Creating commit..."
git commit -m "Initial commit: Receipt categorization system"
echo "✅ Commit created"
echo ""

# Add remote
echo "🔗 Setting up remote repository..."
echo ""
echo "Enter your GitHub repository URL:"
echo "Example: https://github.com/username/receipt-categorization.git"
read repo_url

git remote add origin "$repo_url"
echo "✅ Remote added"
echo ""

# Push to remote
echo "🚀 Pushing to GitHub..."
git push -u origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "================================================"
    echo "  ✅ SUCCESS! Code pushed to GitHub!"
    echo "================================================"
else
    echo ""
    echo "Trying with 'master' branch..."
    git branch -M main
    git push -u origin main
fi

echo ""
echo "Done! Your code is now on GitHub."