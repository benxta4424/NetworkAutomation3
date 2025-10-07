# Network Automation Backend

This backend provides a REST API for orchestrating network device configuration using a testbed YAML file. It is designed to work with a React frontend and automates the configuration of servers, routers, and FTD devices.

## Features

- Upload and validate testbed YAML files
- Step-by-step orchestration of network devices:
  - Load testbed
  - Configure server interfaces and routes
  - Configure routers (via Telnet/SSH)
  - Perform FTD initial setup and API configuration
- Real-time orchestration status tracking
- RESTful API built with Flask
- CORS enabled for frontend integration

## Requirements

- Python 3.8+
- pip

### Python Dependencies

Install required packages:

```bash
pip install flask flask-cors werkzeug pyats bravado bravado-core requests telnetlib3
```

> **Note:** You may need additional dependencies for your environment (e.g., `pyyaml`).

## Usage

1. **Clone the repository** and navigate to the `backend` directory.

2. **Start the Flask API server:**

   ```bash
   python api_server.py
   ```

   The server will run on `http://localhost:5000` by default.

3. **Expose the backend to the internet (Ubuntu/ngrok):**

   If you want to access the backend remotely, use [ngrok](https://ngrok.com/) to tunnel port 5000:

   ```bash
   ngrok http 5000
   ```

   This will provide a public URL you can use to access your backend API from anywhere.

3. **API Endpoints:**

   - `POST /api/upload`  
     Upload a testbed YAML file.  
     Form field: `file` (YAML file)

   - `POST /api/orchestrate`  
     Start orchestration.  
     JSON body: `{ "testbed_file": "your_testbed.yaml" }`

   - `GET /api/status`  
     Get current orchestration status.

   - `GET /api/health`  
     Health check endpoint.

4. **Integrate with Frontend:**  
   Use the provided React frontend or your own client to interact with the API.

## File Structure

- `api_server.py` - Main Flask API server
- `orchestrator.py` - Orchestration logic
- `commands.py` - Device and interface command templates
- `swagger_con.py` - FTD API connector
- `telnet_con.py` - Telnet connection handler
- `rest_con.py` - (If present) REST connection handler
- `*.yaml` - Example testbed files

## Example: Upload and Orchestrate

```bash
# Upload a testbed file
curl -F "file=@copie_testbed1.yaml" http://localhost:5000/api/upload

# Start orchestration
curl -X POST -H "Content-Type: application/json" \
  -d '{"testbed_file": "copie_testbed1.yaml"}' \
  http://localhost:5000/api/orchestrate

# Check status
curl http://localhost:5000/api/status
```

## Notes

- The backend expects to run on a system with access to the network devices defined in your testbed YAML.
- For development, SSL warnings are suppressed.
- Uploaded files are stored in the `uploads/` directory.

## License

This project is for educational and internal use. Adapt as needed for your environment.
