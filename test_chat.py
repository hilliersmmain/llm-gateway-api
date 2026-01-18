#!/usr/bin/env python3
"""Test script to verify /chat endpoint works correctly."""
import requests

BASE_URL = "http://localhost:8000"


def test_chat():
    print("Testing POST /chat...")
    response = requests.post(
        f"{BASE_URL}/chat",
        json={"message": "Hello, this is a test message."}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200


def test_health():
    print("Testing GET /health...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200


if __name__ == "__main__":
    print("=" * 50)
    print("LLM Gateway API - Endpoint Tests")
    print("=" * 50)
    
    health_ok = test_health()
    print()
    chat_ok = test_chat()
    
    print()
    print("=" * 50)
    print(f"Health: {'✓ PASSED' if health_ok else '✗ FAILED'}")
    print(f"Chat:   {'✓ PASSED' if chat_ok else '✗ FAILED'}")
    print("=" * 50)
