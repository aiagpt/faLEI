import json
import os
from models.constants import FREE_TIER_CHARS, SAFE_LIMIT_CHARS

USAGE_FILE = "usage_stats.json"

class UsageTracker:
    def __init__(self):
        self._load()
    
    def _load(self):
        if os.path.exists(USAGE_FILE):
             try:
                 with open(USAGE_FILE, 'r') as f:
                     self.data = json.load(f)
             except:
                 self.data = {"total_chars": 0}
        else:
            self.data = {"total_chars": 0}
            
    def _save(self):
        try:
            with open(USAGE_FILE, 'w') as f:
                json.dump(self.data, f)
        except Exception as e:
            print(f"Erro ao salvar estatísticas de uso: {e}")
            
    def get_usage(self):
        return self.data.get("total_chars", 0)
        
    def add_usage(self, chars: int):
        self.data["total_chars"] = self.get_usage() + chars
        self._save()
        
    def check_can_proceed(self, estimate: int) -> tuple[bool, str]:
        current = self.get_usage()
        projected = current + estimate
        
        if projected > SAFE_LIMIT_CHARS:
            return False, f"LIMITE DE SEGURANÇA ATINGIDO! Tentativa de usar {estimate} chars com {current} já usados. Total projetado: {projected} > {SAFE_LIMIT_CHARS}"
        return True, "OK"
    
    def get_stats(self):
        current = self.get_usage()
        percent = (current / FREE_TIER_CHARS) * 100
        safe_percent = (current / SAFE_LIMIT_CHARS) * 100
        
        return {
            "used": current,
            "limit": FREE_TIER_CHARS,
            "safe_limit": SAFE_LIMIT_CHARS,
            "percent": min(percent, 100),
            "safe_percent": min(safe_percent, 100),
            "remaining_safe": max(0, SAFE_LIMIT_CHARS - current)
        }

# Instância global
usage_tracker = UsageTracker()
