#!/bin/bash
BACKUP_DIR="/Volumes/PREDATOR GM7000 4TB/Mac_Backup_20260702"
mkdir -p "$BACKUP_DIR"

echo "Moving standard directories..."
mv ~/Verantyx_VR_Drive "$BACKUP_DIR/" 2>/dev/null
mv ~/avh_math "$BACKUP_DIR/" 2>/dev/null
mv ~/refactorium-v1-0-0 "$BACKUP_DIR/" 2>/dev/null
mv ~/verantyx_v6 "$BACKUP_DIR/" 2>/dev/null
mv ~/avh_math_202601261108 "$BACKUP_DIR/" 2>/dev/null

echo "Moving Desktop contents..."
mkdir -p "$BACKUP_DIR/Desktop"
rsync -a --remove-source-files ~/Desktop/ "$BACKUP_DIR/Desktop/"
find ~/Desktop -mindepth 1 -type d -empty -delete 2>/dev/null

echo "Moving Downloads contents..."
mkdir -p "$BACKUP_DIR/Downloads"
rsync -a --remove-source-files ~/Downloads/ "$BACKUP_DIR/Downloads/"
find ~/Downloads -mindepth 1 -type d -empty -delete 2>/dev/null

echo "Done!"
