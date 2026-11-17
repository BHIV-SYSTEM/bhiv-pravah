import os
import sys
from pathlib import Path

# Add project root and control_plane directory to path in correct priority order
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
control_plane_dir = os.path.join(root_dir, 'control_plane')

if root_dir not in sys.path:
    sys.path.append(root_dir)
if control_plane_dir not in sys.path:
    sys.path.append(control_plane_dir)

import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", os.getenv("BACKEND_PORT", "8000")))
    # Use full module path for production (FastAPI backend only)
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=port, reload=False)
