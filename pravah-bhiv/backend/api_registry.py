"""Registry API - List all onboarded apps"""

from flask import Blueprint, jsonify
import os
import json
import glob

registry_bp = Blueprint('registry', __name__)

REGISTRY_PATH = "apps/registry"

@registry_bp.route('/list', methods=['GET'])
def list_apps():
    """List all apps in registry"""
    try:
        os.makedirs(REGISTRY_PATH, exist_ok=True)
        
        apps = []
        for json_file in glob.glob(os.path.join(REGISTRY_PATH, "*.json")):
            try:
                with open(json_file, 'r') as f:
                    app_data = json.load(f)
                    apps.append(app_data)
            except:
                pass
        
        return jsonify({
            "status": "success",
            "count": len(apps),
            "apps": apps
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
