import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# API Settings
API_KEY = os.getenv('BYBIT_API_KEY')
API_SECRET = os.getenv('BYBIT_API_SECRET')
TESTNET = os.getenv('TESTNET', 'true').lower() == 'true'

# Trading Parameters
SYMBOL = os.getenv('TRADE_SYMBOL', 'MNTUSDT')
QUANTITY = float(os.getenv('TRADE_QUANTITY', '0.1'))
MAX_POSITION = float(os.getenv('MAX_POSITION_SIZE', '1.0'))
STOP_LOSS_PCT = float(os.getenv('STOP_LOSS_PERCENTAGE', '2.0'))
TAKE_PROFIT_PCT = float(os.getenv('TAKE_PROFIT_PERCENTAGE', '4.0'))

# Monitoring Settings
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '60'))
RETRY_DELAY = int(os.getenv('RETRY_DELAY', '5'))
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3')) 