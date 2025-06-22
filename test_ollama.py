#!/usr/bin/env python3
"""
Ollama Remote Access Test Script - Updated for your setup
"""

import requests
import json
import time

class OllamaTest:
    def __init__(self, host="100.73.210.57", port=11434):
        self.base_url = f"http://{host}:{port}"
        self.api_url = f"{self.base_url}/api"
        self.host = host
        self.port = port
        
    def test_connection(self):
        """Test basic connectivity"""
        print(f"🔍 Testing connection to {self.base_url}...")
        
        try:
            response = requests.get(f"{self.base_url}", timeout=5)
            print("✅ Server is responding")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def list_models(self):
        """List available models"""
        print(f"\n📋 Checking available models...")
        
        try:
            response = requests.get(f"{self.api_url}/tags", timeout=10)
            if response.status_code == 200:
                data = response.json()
                models = data.get('models', [])
                
                if models:
                    print("✅ Available models:")
                    for model in models:
                        name = model.get('name', 'Unknown')
                        print(f"   • {name}")
                    return [model.get('name') for model in models]
                else:
                    print("⚠️  No models found")
                    return []
            else:
                print(f"❌ Failed to list models: {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Error listing models: {e}")
            return []
    
    def test_your_model(self):
        """Test with your exact model and setup"""
        model_name = "hf.co/TheBloke/LLaMA-13b-GGUF:Q5_K_M"
        prompt = "Why"
        
        print(f"\n🤖 Testing your exact setup:")
        print(f"   Model: {model_name}")
        print(f"   Prompt: '{prompt}'")
        
        # Exact payload structure you're using
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False
        }
        
        try:
            start_time = time.time()
            response = requests.post(
                f"{self.api_url}/generate",
                json=payload,
                timeout=30
            )
            end_time = time.time()
            
            print(f"   Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Pretty print the JSON response like jq does
                print("✅ Response JSON:")
                print(json.dumps(data, indent=2))
                
                # Extract key info
                generated_text = data.get('response', '')
                print(f"\n📝 Generated text: '{generated_text}'")
                print(f"⏱️  Response time: {end_time - start_time:.2f} seconds")
                
                return True
            else:
                print(f"❌ Request failed")
                print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def test_autocomplete_prompts(self):
        """Test autocomplete-style prompts with your model"""
        model_name = "hf.co/TheBloke/LLaMA-13b-GGUF:Q5_K_M"
        
        print(f"\n✏️  Testing autocomplete scenarios...")
        
        test_prompts = [
            "The quick brown fox",
            "I think the best",
            "In my opinion",
            "To solve this problem"
        ]
        
        for prompt in test_prompts:
            print(f"\n   Testing: '{prompt}'")
            
            payload = {
                "model": model_name,
                "prompt": prompt,
                "stream": False
            }
            
            try:
                start_time = time.time()
                response = requests.post(
                    f"{self.api_url}/generate",
                    json=payload,
                    timeout=15
                )
                end_time = time.time()
                
                if response.status_code == 200:
                    data = response.json()
                    completion = data.get('response', '').strip()
                    response_time = end_time - start_time
                    
                    print(f"      → '{completion}' ({response_time:.2f}s)")
                else:
                    print(f"      ❌ Failed: {response.status_code}")
            
            except Exception as e:
                print(f"      ❌ Error: {e}")

def main():
    print("Testing your Ollama setup")
    print("=" * 40)
    
    # Use your exact configuration
    tester = OllamaTest(host="100.73.210.57", port=11434)
    
    # Test connection
    if not tester.test_connection():
        return
    
    # List models
    tester.list_models()
    
    # Test your exact curl equivalent
    tester.test_your_model()
    
    # Test autocomplete scenarios
    tester.test_autocomplete_prompts()
    
    print("\n" + "=" * 40)
    print("✅ Testing complete!")

if __name__ == "__main__":
    main()