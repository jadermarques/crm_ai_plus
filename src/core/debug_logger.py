import json
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOGS_DIR = PROJECT_ROOT / "logs" / "debug_runs"

def create_log_session() -> Path:
    """Creates a new unique debug log file and returns its path."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"debug_{timestamp}.jsonl"
    # Create empty file to ensure it exists and is writable
    log_file.touch()
    return log_file

def append_log(log_path: Path | str | None, event_type: str, data: dict) -> None:
    """Appends a structured JSON log entry to the specified file."""
    if not log_path:
        return
        
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        "data": data
    }
    
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        # Fail silently to avoid interrupting the main flow, but print to stderr
        print(f"[DebugLogger] Failed to write log: {e}")
