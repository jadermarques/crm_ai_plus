import sys
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add src to path
sys.path.append(".")

# Mock settings before importing modules that use them
with patch("src.core.config.get_settings") as mock_settings:
    mock_settings.return_value.OPENAI_API_KEY = "sk-test-fake-key"
    
    from src.core.debug_logger import log_llm_interaction

    def test_logging():
        print("Testing logging...")
        log_llm_interaction(
            agent_name="TestAgent",
            model="gpt-test",
            system_prompt="System Test",
            user_prompt="User Test",
            response="Response Test",
            usage={"input": 10, "output": 20, "total": 30}
        )
        print("Log called.")

        # Check if written
        log_file = Path("logs/llm_history.log")
        if not log_file.exists():
            print("ERROR: Log file does not exist.")
            return

        content = log_file.read_text(encoding="utf-8")
        if "Response Test" in content:
            print("SUCCESS: Log entry found.")
        else:
            print("FAILURE: Log entry NOT found.")

    if __name__ == "__main__":
        test_logging()
