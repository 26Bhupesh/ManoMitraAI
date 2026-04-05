import sys, os
sys.path.insert(0, 'backend')

# stub external modules to avoid import errors
import types
sys.modules['fastapi'] = types.SimpleNamespace()
sys.modules['groq'] = types.SimpleNamespace(Groq=lambda api_key=None: None)

# dummy groq client to attach later
class DummyResp:
    def __init__(self, content):
        self.choices=[type('C',(),{'message':type('M',(),{'content':content})})]

class DummyClient:
    class chat:
        class completions:
            @staticmethod
            def create(model,messages,temperature,max_tokens):
                return DummyResp('{"topic":"anxiety","confidence":0.9}')

import app.support_service as ss
ss.client = DummyClient()

print('topic result', ss.detect_topic_llm('I am worried', 'en'))
blocks = ss.load_topic_blocks('anxiety_en.txt')
print('blocks count', len(blocks))
if blocks:
    print(blocks[0])
