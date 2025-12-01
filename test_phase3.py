# docker-compose --env-file .env.dev -f docker-compose.dev.yml exec ai-service python test_phase3.py

import sys
import torch
import asyncio
from src.core.model_engine import model_engine
from src.services.rag_orchestrator import rag_orchestrator

def test_l2_normalization_and_dimension():
    print("--- [Test 1] L2 Normalization & Dimension Check ---")
    text = ["테스트 쿼리"]
    
    # 1. 인코딩
    features = model_engine.encode_text(text)
    tensor_features = torch.tensor(features)
    
    # 2. 차원 확인
    dim = tensor_features.shape[-1]
    print(f"Dimension: {dim}")
    if dim != 768:
        print(f"❌ FAIL: Expected 768, got {dim}")
        sys.exit(1)
    else:
        print(f"✅ PASS: Dimension is 768")

    # 3. L2 Norm 확인 (1.0에 근사해야 함)
    norm = torch.norm(tensor_features, dim=-1).item()
    print(f"L2 Norm: {norm}")
    if abs(norm - 1.0) > 1e-4:
        print(f"❌ FAIL: L2 Norm is not 1.0 (got {norm})")
        sys.exit(1)
    else:
        print(f"✅ PASS: L2 Normalization Applied")

def test_rag_dependencies():
    print("\n--- [Test 2] RAG Orchestrator Dependencies ---")
    if hasattr(rag_orchestrator, 'semaphore'):
        print(f"✅ PASS: Semaphore initialized ({rag_orchestrator.semaphore._value})")
    else:
        print("❌ FAIL: Semaphore missing")

if __name__ == "__main__":
    # Model Engine 초기화 (Singleton)
    try:
        model_engine.initialize()
        test_l2_normalization_and_dimension()
        test_rag_dependencies()
        print("\n🎉 All Phase 3 Critical Checks Passed!")
    except Exception as e:
        print(f"\n❌ Critical Error during test: {e}")
        sys.exit(1)