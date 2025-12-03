#!/usr/bin/env python3
"""
Quick test script for local LLM without downloading
Tests imports and configuration
"""
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_imports():
    """Test if all required modules can be imported"""
    print("=" * 60)
    print("Testing Local LLM Setup")
    print("=" * 60)
    print()
    
    errors = []
    
    # Test standard imports
    print("1. Testing standard imports...")
    try:
        import requests
        print("   ✓ requests")
    except ImportError as e:
        errors.append(f"requests: {e}")
        print(f"   ✗ requests: {e}")
    
    # Test llama-cpp-python
    print("\n2. Testing llama-cpp-python...")
    try:
        from llama_cpp import Llama
        print("   ✓ llama-cpp-python installed")
    except ImportError as e:
        errors.append(f"llama-cpp-python: {e}")
        print(f"   ✗ llama-cpp-python not installed")
        print("      Install with: pip3 install llama-cpp-python")
    
    # Test huggingface-hub
    print("\n3. Testing huggingface-hub...")
    try:
        from huggingface_hub import hf_hub_download
        print("   ✓ huggingface-hub installed")
    except ImportError as e:
        errors.append(f"huggingface-hub: {e}")
        print(f"   ✗ huggingface-hub not installed")
        print("      Install with: pip3 install huggingface-hub")
    
    # Test sentence-transformers
    print("\n4. Testing sentence-transformers...")
    try:
        from sentence_transformers import SentenceTransformer
        print("   ✓ sentence-transformers installed")
    except ImportError as e:
        errors.append(f"sentence-transformers: {e}")
        print(f"   ✗ sentence-transformers not installed")
        print("      Install with: pip3 install sentence-transformers")
    
    # Test faiss
    print("\n5. Testing faiss-cpu...")
    try:
        import faiss
        print("   ✓ faiss-cpu installed")
    except ImportError as e:
        errors.append(f"faiss-cpu: {e}")
        print(f"   ✗ faiss-cpu not installed")
        print("      Install with: pip3 install faiss-cpu")
    
    # Test local modules
    print("\n6. Testing local modules...")
    try:
        from config import Config
        print("   ✓ config.py")
        print(f"      AI_MODE: {Config.AI_MODE}")
        print(f"      LOCAL_MODEL_THREADS: {Config.LOCAL_MODEL_THREADS}")
        print(f"      RAG_ENABLED: {Config.RAG_ENABLED}")
    except Exception as e:
        errors.append(f"config: {e}")
        print(f"   ✗ config.py error: {e}")
    
    try:
        from local_llm import LocalLLM
        print("   ✓ local_llm.py")
    except Exception as e:
        errors.append(f"local_llm: {e}")
        print(f"   ✗ local_llm.py error: {e}")
    
    try:
        from rag_system import RAGSystem
        print("   ✓ rag_system.py")
    except Exception as e:
        errors.append(f"rag_system: {e}")
        print(f"   ✗ rag_system.py error: {e}")
    
    # Check config file
    print("\n7. Checking configuration files...")
    import os
    if os.path.exists('config.env'):
        print("   ✓ config.env exists")
    else:
        print("   ⚠ config.env not found")
        print("      Create it: cp config.env.example config.env")
    
    # Summary
    print("\n" + "=" * 60)
    if errors:
        print(f"✗ Found {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")
        print("\nInstall missing packages:")
        print("  pip3 install -r requirements.txt")
        return False
    else:
        print("✓ All checks passed!")
        print("\nYou can now:")
        print("  1. Run bot: python3 bot.py")
        print("     (Model will download automatically on first run)")
        return True
    print("=" * 60)

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)

