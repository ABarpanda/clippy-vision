"""
Quick test script to verify Clippy Vision installation
Run this after setup to ensure everything is working correctly
"""

import os
import sys


def test_imports():
    """Test if all required Python packages are installed"""
    print("\n[1/5] Testing Python imports...")
    try:
        import imagehash
        import mss
        import psutil
        import win32api
        import win32gui
        from PIL import Image
        from pynput import keyboard
        print("  ✓ All Python packages imported successfully")
        return True
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        print("  Run: pip install -r requirements.txt")
        return False

def test_ollama_connection():
    """Test connection to Ollama"""
    print("\n[2/5] Testing Ollama connection...")
    try:
        from core.llm_gateway import gateway
        result = gateway.embed("test", embed_model="nomic-embed-text", timeout=30)
        if result:
            print("  ✓ Ollama connection successful")
            return True
        print("  ✗ Ollama returned empty embedding")
        return False
    except Exception as e:
        print(f"  ✗ Ollama connection failed: {e}")
        print("  Make sure Ollama is running: ollama serve")
        return False

def test_models():
    """Test if required models are available"""
    print("\n[3/5] Checking installed models...")
    try:
        import subprocess
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            check=True
        )

        models_output = result.stdout
        required_models = ["qwen3:8b", "qwen3-vl:4b", "nomic-embed-text"]
        missing = []

        for model in required_models:
            if model in models_output:
                print(f"  ✓ {model}")
            else:
                print(f"  ✗ {model} (missing)")
                missing.append(model)

        if missing:
            print(f"\n  To install missing models:")
            for model in missing:
                print(f"    ollama pull {model}")
            return False
        return True
    except Exception as e:
        print(f"  ✗ Error checking models: {e}")
        return False

def test_directories():
    """Test if required directories exist"""
    print("\n[4/5] Checking project directories...")
    dirs = [
        "core/data",
        "core/data/screenshots",
        "logs"
    ]

    all_exist = True
    for dir_path in dirs:
        if os.path.exists(dir_path):
            print(f"  ✓ {dir_path}")
        else:
            print(f"  ✗ {dir_path} (missing)")
            all_exist = False

    if not all_exist:
        print("  Run setup script to create missing directories")
    return all_exist

def test_database():
    """Test database initialization"""
    print("\n[5/5] Testing database...")
    try:
        from core.storage import conn

        # Check if main tables exist
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = [row[0] for row in cursor.fetchall()]

        required_tables = ["events", "sessions", "memory_clusters", "memory_facts", "conversations"]
        missing_tables = [t for t in required_tables if t not in tables]

        if missing_tables:
            print(f"  ✗ Missing tables: {missing_tables}")
            return False

        print(f"  ✓ Database initialized with {len(tables)} tables")

        # Check event count
        event_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        print(f"  ✓ Database contains {event_count} events")

        return True
    except Exception as e:
        print(f"  ✗ Database error: {e}")
        return False

def main():
    print("=" * 50)
    print("  Clippy Vision - Installation Test")
    print("=" * 50)

    results = []

    results.append(("Python Imports", test_imports()))
    results.append(("Ollama Connection", test_ollama_connection()))
    results.append(("AI Models", test_models()))
    results.append(("Directories", test_directories()))
    results.append(("Database", test_database()))

    print("\n" + "=" * 50)
    print("  Test Summary")
    print("=" * 50)

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}  {test_name}")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print("\n✓ All tests passed! Clippy Vision is ready to use.")
        print("\nNext steps:")
        print("  1. Start capture: python core\\screen_capture.py")
        print("  2. Chat with Clippy: python agent\\react_agent.py")
    else:
        print("\n✗ Some tests failed. Please fix the issues above.")
        print("  See QUICKSTART.md for troubleshooting help.")
        sys.exit(1)

if __name__ == "__main__":
    main()
