# ai_n8n.py
# تحسينات: Connection pooling، أفضل error handling، retry logic محسّن

import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from Config import Config

class N8nClient:
    def __init__(self, config: Config = None):
        self.cfg = config or Config()
        self.url = self.cfg.N8N_URL
        self.timeout = self.cfg.HTTP_TIMEOUT
        self.max_retries = self.cfg.RETRIES

        # ✅ Session مع connection pooling للسرعة
        self.session = requests.Session()
        
        # ✅ Retry strategy محسّنة
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=0.3,  # 0.3s, 0.6s, 1.2s
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"]
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=2,  # عدد الـ connections المفتوحة
            pool_maxsize=5       # أقصى حجم للـ pool
        )
        
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        # ✅ Headers ثابتة
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "AI-Robot/1.0"
        })

    def chat(self, userId: str, message: str) -> str:
        """
        إرسال رسالة للـ AI Agent عبر n8n
        
        Args:
            session_id: معرّف الجلسة
            message: الرسالة النصية
            
        Returns:
            الرد من الـ AI أو string فارغ عند الفشل
        """
        if not message or not message.strip():
            return ""

        payload = {
            "userId": userId,
            "activeAgent":"general",
            "message": message.strip()
        }

        start_time = time.time()

        try:
            # ✅ استخدام session للـ connection reuse
            resp = self.session.post(
                self.url,
                json=payload,
                timeout=self.timeout
            )
            
            elapsed = time.time() - start_time
            
            # ✅ معالجة أفضل للـ status codes
            if resp.status_code == 200:
                try:
                    js = resp.json()
                except ValueError:
                    # النص العادي
                    output = resp.text.strip()
                    print(f"[n8n] ✅ Response (text) in {elapsed:.2f}s")
                    print(f"[n8n] ✅ Response (text) in {resp}")
                    return output

                # ✅ محاولة استخراج الرد من JSON
                if isinstance(js, dict):
                    # Try multiple possible keys
                    output = (
                        js.get("output") or 
                        js.get("message") or 
                        js.get("response") or 
                        js.get("text") or
                        ""
                    )
                    
                    if output:
                        print(f"[n8n] ✅ Response (JSON) in {elapsed:.2f}s")
                        return str(output).strip()
                    
                    # إذا لم نجد الرد، نطبع JSON للتشخيص
                    print(f"[n8n] ⚠️ Unexpected JSON structure: {js}")
                    return str(js).strip()

                # JSON ليس dict
                print(f"[n8n] ⚠️ Non-dict JSON: {js}")
                return str(js).strip()

            elif resp.status_code == 429:
                print(f"[n8n] ⚠️ Rate limited (429)")
                return ""
                
            elif resp.status_code >= 500:
                print(f"[n8n] ❌ Server error ({resp.status_code})")
                return ""
                
            else:
                print(f"[n8n] ❌ Unexpected status: {resp.status_code}")
                return ""

        except requests.Timeout:
            print(f"[n8n] ⏱️ Timeout after {self.timeout}s")
            return ""
            
        except requests.ConnectionError as e:
            print(f"[n8n] 🔌 Connection error: {e}")
            return ""
            
        except requests.RequestException as e:
            print(f"[n8n] ❌ Request error: {e}")
            return ""
            
        except Exception as e:
            print(f"[n8n] ❌ Unexpected error: {e}")
            return ""

    def close(self):
        """إغلاق الـ session"""
        try:
            self.session.close()
        except Exception:
            pass

    def __del__(self):
        """Cleanup عند الحذف"""
        self.close()


# ✅ Test function
if __name__ == "__main__":
    import os
    
    # تأكد من وجود N8N_URL في البيئة
    if not os.getenv("N8N_URL"):
        print("❌ Please set N8N_URL environment variable")
        exit(1)
    
    cfg = Config()
    client = N8nClient(cfg)
    
    print("Testing n8n connection...")
    response = client.chat("test-session", "Hello, how are you?")
    
    if response:
        print(f"✅ Response: {response}")
    else:
        print("❌ No response received")
    
    client.close()
