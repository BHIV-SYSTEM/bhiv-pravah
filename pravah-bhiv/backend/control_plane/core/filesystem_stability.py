#!/usr/bin/env python3
"""
Filesystem Stability Module
Handles path construction and OneDrive/sync folder issues
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional, List

class FilesystemStabilityManager:
    """Manages filesystem operations with stability guarantees."""
    
    @staticmethod
    def get_stable_path(*path_parts) -> str:
        """
        Construct stable path using os.path.join() - no hardcoded paths.
        
        Args:
            *path_parts: Path components to join
            
        Returns:
            Properly constructed path for current OS
        """
        if not path_parts:
            return os.getcwd()
        
        # Use os.path.join for cross-platform compatibility
        return os.path.join(*path_parts)
    
    @staticmethod
    def ensure_directory(path: str) -> bool:
        """
        Ensure directory exists with proper error handling.
        
        Args:
            path: Directory path to create
            
        Returns:
            True if directory exists or was created successfully
        """
        try:
            os.makedirs(path, exist_ok=True)
            return True
        except (OSError, PermissionError) as e:
            print(f"ERROR: Cannot create directory {path}: {e}")
            return False
    
    @staticmethod
    def is_synced_folder(path: str) -> bool:
        """
        Check if path is in a synced folder (OneDrive, Dropbox, etc.).
        
        Args:
            path: Path to check
            
        Returns:
            True if path appears to be in a synced folder
        """
        path_lower = path.lower()
        sync_indicators = [
            'onedrive', 'dropbox', 'google drive', 'icloud',
            'box sync', 'sync', 'cloud'
        ]
        
        return any(indicator in path_lower for indicator in sync_indicators)
    
    @staticmethod
    def get_stable_workspace() -> str:
        """
        Get stable workspace location outside synced folders.
        
        Returns:
            Path to stable workspace directory
        """
        # Try common stable locations
        stable_locations = [
            os.path.join(os.path.expanduser("~"), "workspace"),
            os.path.join("C:", "dev") if os.name == 'nt' else os.path.join("/", "tmp", "workspace"),
            os.path.join(tempfile.gettempdir(), "workspace")
        ]
        
        for location in stable_locations:
            try:
                if FilesystemStabilityManager.ensure_directory(location):
                    if not FilesystemStabilityManager.is_synced_folder(location):
                        return location
            except Exception:
                continue
        
        # Fallback to temp directory
        return tempfile.mkdtemp(prefix="stable_workspace_")
    
    @staticmethod
    def migrate_from_synced_folder(current_path: str, target_path: Optional[str] = None) -> str:
        """
        Migrate repository from synced folder to stable location.
        
        Args:
            current_path: Current repository path
            target_path: Target path (optional, will choose stable location if None)
            
        Returns:
            New stable path
        """
        if not FilesystemStabilityManager.is_synced_folder(current_path):
            print(f"Path {current_path} is already stable")
            return current_path
        
        if target_path is None:
            stable_workspace = FilesystemStabilityManager.get_stable_workspace()
            target_path = os.path.join(stable_workspace, "Multi-Agent-CICD")
        
        print(f"Migrating from synced folder:")
        print(f"  From: {current_path}")
        print(f"  To: {target_path}")
        
        try:
            # Ensure target directory exists
            FilesystemStabilityManager.ensure_directory(os.path.dirname(target_path))
            
            # Copy repository to stable location
            if os.path.exists(target_path):
                print(f"Target already exists, removing: {target_path}")
                shutil.rmtree(target_path)
            
            shutil.copytree(current_path, target_path)
            print(f"Migration completed successfully to: {target_path}")
            
            return target_path
            
        except Exception as e:
            print(f"ERROR: Migration failed: {e}")
            raise
    
    @staticmethod
    def validate_path_stability(path: str) -> dict:
        """
        Validate path stability and provide recommendations.
        
        Args:
            path: Path to validate
            
        Returns:
            Validation results dictionary
        """
        results = {
            'path': path,
            'stable': True,
            'issues': [],
            'recommendations': []
        }
        
        # Check if in synced folder
        if FilesystemStabilityManager.is_synced_folder(path):
            results['stable'] = False
            results['issues'].append('Path is in synced folder (OneDrive, etc.)')
            results['recommendations'].append('Move to stable location outside sync folders')
        
        # Check write permissions
        try:
            test_file = os.path.join(path, '.stability_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
        except Exception as e:
            results['stable'] = False
            results['issues'].append(f'Write permission issue: {e}')
            results['recommendations'].append('Check directory permissions')
        
        # Check path length (Windows limitation)
        if os.name == 'nt' and len(path) > 240:
            results['stable'] = False
            results['issues'].append('Path too long for Windows')
            results['recommendations'].append('Use shorter path')
        
        return results

def fix_hardcoded_paths_in_file(file_path: str) -> int:
    """
    Fix hardcoded paths in a Python file by replacing with os.path.join().
    
    Args:
        file_path: Path to Python file to fix
        
    Returns:
        Number of fixes applied
    """
    if not os.path.exists(file_path):
        return 0
    
    fixes_applied = 0
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Common hardcoded path patterns to fix
        patterns = [
            (r'os.path.join("logs", r"([^")]+)"', r'os.path.join("logs", r"\1")'),
            (r'os.path.join("environments", r"([^")]+)"', r'os.path.join("environments", r"\1")'),
            (r'os.path.join("core", r"([^")]+)"', r'os.path.join("core", r"\1")'),
            (r'os.path.join("agents", r"([^")]+)"', r'os.path.join("agents", r"\1")'),
        ]
        
        import re
        for pattern, replacement in patterns:
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                fixes_applied += 1
                content = new_content
        
        # Write back if changes were made
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
    except Exception as e:
        print(f"ERROR: Could not fix paths in {file_path}: {e}")
    
    return fixes_applied