import threading

class ThreadSafeDict:
    def __init__(self):
        self.data = {}
        self.lock = threading.Lock()

    def set(self, key, value):
        with self.lock:
            self.data[key] = value

    def get(self, key):
        with self.lock:
            return self.data.get(key)

    def __contains__(self, key):
        with self.lock:
            return key in self.data

    def __delitem__(self, key):
        with self.lock:
            del self.data[key]
