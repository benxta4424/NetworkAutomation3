import asyncio
import os
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
import urllib3
import sys

# Add current directory and parent project folder to path so imports inside orchestrator work
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)
parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

try:
    from orchestrator import NetworkOrchestrator
    ORCHESTRATOR_AVAILABLE = True
except ImportError as e:
    print(f"Failed to import NetworkOrchestrator: {e}")
    ORCHESTRATOR_AVAILABLE = False

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def create_app():
    app = Flask(__name__)
    CORS(app)

    UPLOAD_FOLDER = 'uploads'
    ALLOWED_EXTENSIONS = {'yaml', 'yml'}

    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    # Global orchestration status
    app.orchestration_status = {
        'current_step': 0,
        'steps': [
            {'id': 1, 'name': 'Load testbed', 'completed': False, 'inProgress': False, 'message': ''},
            {'id': 2, 'name': 'Server interfaces', 'completed': False, 'inProgress': False, 'message': ''},
            {'id': 3, 'name': 'Router Configuration', 'completed': False, 'inProgress': False, 'message': ''},
            {'id': 4, 'name': 'FTD Initial setup', 'completed': False, 'inProgress': False, 'message': ''},
            {'id': 5, 'name': 'FTD API Configuration', 'completed': False, 'inProgress': False, 'message': ''}
        ],
        'isRunning': False,
        'error': None
    }

    app.status_lock = threading.Lock()

    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    def status_callback(step_id, completed=False, in_progress=False, message=""):
        """Callback function to update status from orchestrator"""
        with app.status_lock:
            for step in app.orchestration_status['steps']:
                if step['id'] == step_id:
                    step['completed'] = completed
                    step['inProgress'] = in_progress
                    step['message'] = message
                    if completed:
                        app.orchestration_status['current_step'] = step_id
                    break
            print(f"[CALLBACK] Step {step_id}: completed={completed}, inProgress={in_progress}, message='{message}'")

    def reset_status():
        """Reset all status to initial state"""
        with app.status_lock:
            app.orchestration_status = {
                'current_step': 0,
                'steps': [
                    {'id': 1, 'name': 'Load testbed', 'completed': False, 'inProgress': False, 'message': ''},
                    {'id': 2, 'name': 'Server interfaces', 'completed': False, 'inProgress': False, 'message': ''},
                    {'id': 3, 'name': 'Router Configuration', 'completed': False, 'inProgress': False, 'message': ''},
                    {'id': 4, 'name': 'FTD Initial setup', 'completed': False, 'inProgress': False, 'message': ''},
                    {'id': 5, 'name': 'FTD API Configuration', 'completed': False, 'inProgress': False, 'message': ''}
                ],
                'isRunning': False,
                'error': None
            }

    # API Routes
    @app.route('/api/upload', methods=['POST'])
    def upload_testbed():
        try:
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400

            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400

            if not allowed_file(file.filename):
                return jsonify({'error': 'Only YAML files are allowed'}), 400

            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            reset_status()
            return jsonify({
                'message': 'File uploaded successfully',
                'filename': filename,
                'filepath': filepath
            }), 200

        except Exception as e:
            return jsonify({'error': f'Upload failed: {str(e)}'}), 500

    @app.route('/api/orchestrate', methods=['POST'])
    def start_orchestration():
        try:
            if not ORCHESTRATOR_AVAILABLE:
                return jsonify({'error': 'Orchestrator not available'}), 500

            data = request.get_json()
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400

            testbed_file = data.get('testbed_file')
            if not testbed_file:
                return jsonify({'error': 'No testbed file specified'}), 400

            filepath = os.path.join(app.config['UPLOAD_FOLDER'], testbed_file)
            if not os.path.exists(filepath):
                return jsonify({'error': 'Testbed file not found'}), 404

            # Reset and start orchestration
            reset_status()
            with app.status_lock:
                app.orchestration_status['isRunning'] = True

            # Start orchestration in background thread
            thread = threading.Thread(
                target=run_orchestration_async,
                args=(app, filepath, status_callback)
            )
            thread.daemon = True
            thread.start()

            return jsonify({
                'message': 'Orchestration started successfully',
                'status': app.orchestration_status
            }), 200

        except Exception as e:
            print(f"[ERROR] Failed to start orchestration: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/status', methods=['GET'])
    def get_status():
        with app.status_lock:
            return jsonify(app.orchestration_status), 200

    @app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({
            'status': 'healthy',
            'orchestrator_available': ORCHESTRATOR_AVAILABLE,
            'service': 'Network Orchestrator API'
        }), 200

    return app


def run_orchestration_async(app_instance, testbed_path, status_callback):
    """Run orchestration in a new event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_orchestration(app_instance, testbed_path, status_callback))
    except Exception as e:
        print(f"Orchestration error: {e}")
        with app_instance.status_lock:
            app_instance.orchestration_status['error'] = str(e)
            app_instance.orchestration_status['isRunning'] = False
    finally:
        loop.close()


async def run_orchestration(app_instance, testbed_path, status_callback):
    """Run the full orchestration process"""
    try:
        print("\n" + "=" * 50)
        print("STARTING ORCHESTRATION")
        print("=" * 50)

        # Create orchestrator with status callback
        orchestrator = NetworkOrchestrator(test_bed=testbed_path, status_callback=status_callback)

        # Run full orchestration
        results = await orchestrator.full_orchestration()

        # Final status update
        success = all(results.values()) if results else False
        with app_instance.status_lock:
            app_instance.orchestration_status['isRunning'] = False
            if success:
                print("\n✓ ORCHESTRATION COMPLETED SUCCESSFULLY")
                # mark all steps completed if not already done
                for step in app_instance.orchestration_status['steps']:
                    step['completed'] = True
                    step['inProgress'] = False
            else:
                print("\n✗ ORCHESTRATION FAILED")
                app_instance.orchestration_status['error'] = "Some steps failed - check logs"

    except Exception as e:
        print(f"\n[ORCHESTRATION ERROR] {e}")
        import traceback
        traceback.print_exc()
        with app_instance.status_lock:
            app_instance.orchestration_status['error'] = str(e)
            app_instance.orchestration_status['isRunning'] = False


app = create_app()

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("NETWORK ORCHESTRATOR API SERVER")
    print("=" * 60)
    print(f"Orchestrator available: {ORCHESTRATOR_AVAILABLE}")
    print("Server running on: http://0.0.0.0:5000")
    print("API endpoints: /api/upload, /api/orchestrate, /api/status")
    print("=" * 60 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)