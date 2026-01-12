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

def log_llm_interaction(
    agent_name: str | None,
    model: str,
    system_prompt: str,
    user_prompt: str,
    response: str,
    usage: dict | None = None
) -> None:
    """
    Logs LLM interaction details to a human-readable text file.
    
    Format:
    --------------------------------------------------
    [TIMESTAMP]
    AGENT: <agent_name>
    MODEL: <model>
    
    >>> SYSTEM PROMPT:
    ...
    
    >>> USER PROMPT:
    ...
    
    <<< RESPONSE:
    ...
    
    (Tokens: Input=X, Output=Y, Total=Z)
    --------------------------------------------------
    """
    try:
        log_file = PROJECT_ROOT / "logs" / "llm_history.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        usage_str = ""
        if usage:
            usage_str = f"\n(Tokens: Input={usage.get('input',0)}, Output={usage.get('output',0)}, Total={usage.get('total',0)})"

        divider = "-" * 80
        
        entry = (
            f"\n{divider}\n"
            f"[{timestamp}]\n"
            f"AGENT: {agent_name or 'Unknown'}\n"
            f"MODEL: {model}\n\n"
            f">>> SYSTEM PROMPT:\n{system_prompt}\n\n"
            f">>> USER PROMPT:\n{user_prompt}\n\n"
            f"<<< RESPONSE:\n{response}\n"
            f"{usage_str}\n"
            f"{divider}\n"
        )
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry)
            
    except Exception as e:
        print(f"[DebugLogger] Failed to write LLM log: {e}")
