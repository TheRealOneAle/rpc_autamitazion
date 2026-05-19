from flask import Flask, jsonify, send_file
import os
import subprocess
import sys
import requests
import time

app = Flask(__name__)

# Service URLs
GLOBOS_SERVICE_URL = os.environ.get("GLOBOS_SERVICE_URL", "http://generarglobos:5000")
TABLA_SERVICE_URL = os.environ.get("TABLA_SERVICE_URL", "http://generartabla:5002")
COACH_SERVICE_URL = os.environ.get("COACH_SERVICE_URL", "http://coach-service:5003")

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
        
        # Step 2: Always regenerate tabla (so RabbitMQ event is always published)
        generate_response = requests.post(f"{TABLA_SERVICE_URL}/generate", timeout=60)
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

@app.route('/coaches', methods=['POST'])
def proxy_create_coach():
    from flask import request
    r = requests.post(f"{COACH_SERVICE_URL}/coaches", json=request.get_json(), timeout=10)
    return (r.content, r.status_code, {'Content-Type': 'application/json'})

@app.route('/coaches', methods=['GET'])
def proxy_list_coaches():
    r = requests.get(f"{COACH_SERVICE_URL}/coaches", timeout=10)
    return (r.content, r.status_code, {'Content-Type': 'application/json'})

@app.route('/teams', methods=['GET'])
def proxy_list_teams():
    r = requests.get(f"{COACH_SERVICE_URL}/teams", timeout=10)
    return (r.content, r.status_code, {'Content-Type': 'application/json'})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))