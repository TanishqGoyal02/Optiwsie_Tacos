# Shared state between agent.py and dashboard.py
import threading

class SharedState:
    def __init__(self):
        self.capture_response = True
        self.current_response = ""
        self.lock = threading.Lock()
    
    def set_capture(self, value):
        with self.lock:
            self.capture_response = value
    
    def get_capture(self):
        with self.lock:
            return self.capture_response
    
    def append_response(self, chunk):
        with self.lock:
            if self.capture_response:
                self.current_response += chunk
    
    def get_response(self):
        with self.lock:
            return self.current_response
    
    def clear_response(self):
        with self.lock:
            self.current_response = ""

# Global instance
shared_state = SharedState() 