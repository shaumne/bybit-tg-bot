import os
from dotenv import load_dotenv
import json
from pathlib import Path

class Settings:
    def __init__(self):
        load_dotenv()
        
        # Bot settings
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        if not self.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN not found! Please check your .env file.")
        
        # Trading settings
        self.SYMBOL = os.getenv('TRADE_SYMBOL', 'MNTUSDT')
        self.QUANTITY = float(os.getenv('TRADE_QUANTITY', '0.1'))
        self.STOP_LOSS_PCT = float(os.getenv('STOP_LOSS_PERCENTAGE', '2.0'))
        self.TAKE_PROFIT_PCT = float(os.getenv('TAKE_PROFIT_PERCENTAGE', '4.0'))
        self.MAX_POSITION = float(os.getenv('MAX_POSITION_SIZE', '1.0'))
        
        # API settings
        self.API_KEY = os.getenv('BYBIT_API_KEY')
        self.API_SECRET = os.getenv('BYBIT_API_SECRET')
        self.TESTNET = os.getenv('TESTNET', 'true').lower() == 'true'
        
        # Other settings
        self.CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '60'))
        self.RETRY_DELAY = int(os.getenv('RETRY_DELAY', '5'))
        self.MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
        self.BOT_PASSWORD = None
        
        # Settings file path
        self.settings_file = Path('config/user_settings.json')
        self.load_saved_settings()

    def load_saved_settings(self):
        """Kaydedilmiş ayarları yükle"""
        if self.settings_file.exists():
            with open(self.settings_file, 'r') as f:
                saved_settings = json.load(f)
                for key, value in saved_settings.items():
                    if hasattr(self, key):
                        setattr(self, key, value)

    def save_settings(self):
        """Mevcut ayarları dosyaya kaydet"""
        settings_dict = {
            'SYMBOL': self.SYMBOL,
            'QUANTITY': self.QUANTITY,
            'STOP_LOSS_PCT': self.STOP_LOSS_PCT,
            'TAKE_PROFIT_PCT': self.TAKE_PROFIT_PCT,
            'MAX_POSITION': self.MAX_POSITION,
            'BOT_PASSWORD': self.BOT_PASSWORD
        }
        
        self.settings_file.parent.mkdir(exist_ok=True)
        with open(self.settings_file, 'w') as f:
            json.dump(settings_dict, f, indent=4)

    def set_password(self, password: str):
        """Bot şifresini ayarla ve kaydet"""
        self.BOT_PASSWORD = password
        self.save_settings()

    def verify_password(self, password: str) -> bool:
        """Şifreyi doğrula"""
        return self.BOT_PASSWORD == password

# Global settings instance oluştur
settings = Settings()

# Export settings instance
__all__ = ['settings'] 