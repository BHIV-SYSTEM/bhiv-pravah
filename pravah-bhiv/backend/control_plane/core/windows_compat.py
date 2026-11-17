"""Windows compatibility utilities for Unicode handling."""
import sys
import io

def fix_windows_encoding():
    """Fix Windows console encoding to support Unicode characters."""
    if sys.platform == 'win32':
        try:
            # Set UTF-8 encoding for stdout/stderr
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        except (AttributeError, io.UnsupportedOperation):
            pass  # Already wrapped or not supported

def safe_print(text):
    """Print text with fallback for Unicode errors."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Replace problematic characters with ASCII equivalents
        safe_text = text.encode('ascii', errors='replace').decode('ascii')
        print(safe_text)

# Auto-fix on import
fix_windows_encoding()
