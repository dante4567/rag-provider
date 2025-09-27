#!/bin/bash

# Create necessary volume directories for Docker Compose

echo "Creating volume directories..."

# Create main volumes directory
mkdir -p volumes

# Create ChromaDB data directory
mkdir -p volumes/chroma_data

# Create main data directories
mkdir -p data/input
mkdir -p data/output
mkdir -p data/processed
mkdir -p data/obsidian

# Set permissions
chmod 755 volumes
chmod 755 volumes/chroma_data
chmod 755 data
chmod 755 data/*

echo "Volume directories created successfully!"
echo ""
echo "Directory structure:"
echo "volumes/"
echo "├── chroma_data/          # ChromaDB persistent storage"
echo "data/"
echo "├── input/               # Auto-processed files"
echo "├── output/              # Generated markdown"
echo "├── processed/           # Completed files"
echo "└── obsidian/            # Obsidian vault files"