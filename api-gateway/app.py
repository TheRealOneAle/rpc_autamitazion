from flask import Flask, jsonify, send_file
import os
import subprocess
import sys
import requests
import time

app = Flask(__name__)

# Service URLs
GLOBOS_SERVICE_URL = "http://generarglobos:5000"
TABLA_SERVICE_URL = "http://generartabla:5002"

@app.route('/generate-table', methods=['POST'])
def generate_table():
    try:
        # Step 1: Check if globos are generated, if not, generate them
        globos_response = requests.get(f"{GLOBOS_SERVICE_URL}/status", timeout=10)
        if globos_response.status_code == 200:
            globos_status = globos_response.json()
            if globos_status.get("status") != "complete":
                # Generate globos
                generate_response = requests.post(f"{GLOBOS_SERVICE_URL}/generate", timeout=30)
                if generate_response.status_code != 200:
                    return jsonify({
                        "status": "error", 
                        "message": f"Failed to generate globos: {generate_response.text}"
                    }), 500
        
        # Step 2: Check if tabla is generated, if not, generate it
        # We'll check by trying to fetch the image
        tabla_check_response = requests.get(f"{TABLA_SERVICE_URL}/ranking.jpg", timeout=10)
        if tabla_check_response.status_code != 200:
            # Generate tabla
            generate_response = requests.post(f"{TABLA_SERVICE_URL}/generate", timeout=30)
            if generate_response.status_code != 200:
                return jsonify({
                    "status": "error", 
                    "message": f"Failed to generate tabla: {generate_response.text}"
                }), 500
        
        # Step 3: Return success
        return jsonify({
            "status": "success", 
            "message": "Table generated successfully",
            "table_url": "/table-image"
        }), 200
        
    except requests.exceptions.RequestException as e:
        return jsonify({
            "status": "error", 
            "message": f"Service communication error: {str(e)}"
        }), 500
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": f"Internal error: {str(e)}"
        }), 500

@app.route('/table-image', methods=['GET'])
def get_table_image():
    try:
        # Proxy the image from the tabla service
        response = requests.get(f"{TABLA_SERVICE_URL}/ranking.jpg", timeout=10)
        if response.status_code == 200:
            return response.content, 200, {'Content-Type': 'image/jpeg'}
        else:
            return jsonify({
                "status": "error", 
                "message": "Table image not available"
            }), 404
    except requests.exceptions.RequestException as e:
        return jsonify({
            "status": "error", 
            "message": f"Failed to fetch table image: {str(e)}"
        }), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)