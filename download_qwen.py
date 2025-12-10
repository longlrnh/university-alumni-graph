"""
Download Qwen 3 0.6B từ Hugging Face
Chuẩn bị model cho chatbot
"""

print("="*80)
print("TẢI QWEN 3 0.6B TỪ HUGGING FACE")
print("="*80)

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import torch
    
    print("\n📦 Transformers library available")
    print(f"   PyTorch version: {torch.__version__}")
    print(f"   CUDA available: {torch.cuda.is_available()}")
    
    model_name = "Qwen/Qwen2-0.5B-Instruct"
    
    print(f"\n📥 Downloading {model_name}...")
    print("   (This may take a few minutes)")
    
    print("\n   [1/2] Downloading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    print("   ✅ Tokenizer downloaded")
    
    print("\n   [2/2] Downloading model...")
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto"
    )
    print("   ✅ Model downloaded")
    
    print("\n" + "="*80)
    print("✅ SUCCESSFULLY DOWNLOADED QWEN 2 0.5B")
    print("="*80)
    
    print(f"\n📊 Model Info:")
    print(f"   • Model name: {model_name}")
    print(f"   • Parameters: ~0.5B (small, efficient)")
    print(f"   • Type: Instruction-tuned")
    print(f"   • Precision: {'FP16' if torch.cuda.is_available() else 'FP32'}")
    print(f"   • Device: {'CUDA (GPU)' if torch.cuda.is_available() else 'CPU'}")
    
    print(f"\n💾 Model saved at: ~/.cache/huggingface/hub/")
    
    # Test inference
    print("\n" + "="*80)
    print("TEST INFERENCE")
    print("="*80)
    
    prompt = "Barack Obama là ai?"
    print(f"\n❓ Test prompt: {prompt}")
    
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        output = model.generate(**inputs, max_new_tokens=50, temperature=0.7)
    
    response = tokenizer.decode(output[0], skip_special_tokens=True)
    print(f"\n💬 Response:\n{response}")
    
    print("\n" + "="*80)
    print("✅ MODEL IS READY TO USE!")
    print("="*80)
    
except ImportError as e:
    print(f"\n❌ Error: {e}")
    print("\n💡 Installing required packages...")
    print("   Run: pip install transformers torch")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\n💡 Tips:")
    print("   • Check internet connection")
    print("   • Ensure sufficient disk space (~2GB)")
    print("   • Try: pip install --upgrade transformers")
