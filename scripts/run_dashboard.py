"""
Run the dashboard on port 5001.
Managed by systemd — see rns-trader-dashboard.service
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard.app import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
