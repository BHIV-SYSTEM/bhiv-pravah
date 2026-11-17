import time
from flask import Flask

app = Flask(__name__)

failure_state = False

@app.route("/")
def home():
    return "Web1 Service Running"

@app.route("/simulate-failure", methods=["POST"])
def simulate_failure():
    global failure_state
    failure_state = True
    return {"status": "failure_simulated"}

@app.route("/health")
def health():
    global failure_state
    if failure_state:
        time.sleep(1.0)
        return {"status": "degraded"}, 200
    return {"status": "healthy"}, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)