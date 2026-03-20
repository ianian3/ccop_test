
import os
import sys
from flask import Flask
from config import Config

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.ai_service import AIService

def trigger_log():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    with app.app_context():
        print("🚀 Triggering AIService.generate_cypher to test SFT logging...")
        # This will call the modified generate_cypher which includes _log_for_sft
        cypher = AIService.generate_cypher("특정 계좌(123-456)의 소유자를 찾아줘", graph_path="tccop_graph_v6")
        print(f"✅ Generated Cypher: {cypher}")
        
        log_file = os.path.join(app.root_path, 'data', 'sft_training_raw.jsonl')
        if os.path.exists(log_file):
            print(f"🎉 Success! Log file created at: {log_file}")
            with open(log_file, 'r', encoding='utf-8') as f:
                print(f"📄 Content: {f.read()}")
        else:
            print(f"❌ Log file NOT found at: {log_file}")

if __name__ == "__main__":
    trigger_log()
