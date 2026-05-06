from flask import Flask, jsonify
import os
import subprocess
import sys

app = Flask(__name__)

# Path to the globos generation script
SCRIPT_PATH = os.path.join(os.path.dirname(__file__), 'generarglobos.py')
# Directory where globos are stored
GLOBOS_DIR = os.path.join(os.path.dirname(__file__), 'globosgenerados')

@app.route('/generate', methods=['POST'])
def generate_globos():
    # Check if globos are already generated
    if not os.path.exists(GLOBOS_DIR):
        os.makedirs(GLOBOS_DIR)
    
    # Check if we have the expected globos (A.png to M.png)
    expected_globos = [f"{chr(i)}.png" for i in range(65, 78)]  # A to M
    missing_globos = [g for g in expected_globos if not os.path.exists(os.path.join(GLOBOS_DIR, g))]
    
    if not missing_globos:
        return jsonify({"status": "success", "message": "Globos already generated"}), 200
    
    # Import and run the generation function directly
    try:
        # Make sure globosgenerados directory exists
        os.makedirs(GLOBOS_DIR, exist_ok=True)
        
        # Import the module and call the function
        import importlib.util
        spec = importlib.util.spec_from_file_location("generarglobos_mod", SCRIPT_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        
        success, msg = mod.generar_globos()
        if success:
            return jsonify({"status": "success", "message": msg}), 200
        else:
            return jsonify({"status": "error", "message": msg}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/status', methods=['GET'])
def status():
    # Check if we have the expected globos
    expected_globos = [f"{chr(i)}.png" for i in range(65, 78)]  # A to M
    missing_globos = [g for g in expected_globos if not os.path.exists(os.path.join(GLOBOS_DIR, g))]
    
    if missing_globos:
        return jsonify({"status": "pending", "missing": missing_globos}), 200
    else:
        return jsonify({"status": "complete"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)