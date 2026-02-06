
import sys
import os
from pathlib import Path

# Add the project root to sys.path so that "app" module can be found
# structure: src/modules/ai_service/app/tests/conftest.py
# we want to add src/modules/ai_service to path

current_dir = Path(__file__).parent.absolute()
root_dir = current_dir.parent.parent  # src/modules/ai_service
sys.path.insert(0, str(root_dir))
