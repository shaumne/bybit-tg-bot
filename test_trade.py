from modules.trade import TradeExecutor
from modules.telegram_bot import TelegramBot
from utils.logger import setup_logger
import os
from dotenv import load_dotenv

# Load .env
load_dotenv()

logger = setup_logger('trade_test')

def test_bybit_connection():
    """Test Bybit API connection"""
    try:
        trader = TradeExecutor()
        
        # Test API connection
        logger.info("Testing Bybit API connection...")
        
        # Test message
        telegram = TelegramBot()
        test_message = "🧪 <b>Bybit API Test</b>\n\n"
        
        # Testnet/Mainnet status
        is_testnet = os.getenv('TESTNET', 'true').lower() == 'true'
        test_message += f"📡 Network: {'Testnet' if is_testnet else 'Mainnet'}\n"
        
        # API Key check
        api_key = os.getenv('BYBIT_API_KEY')
        test_message += f"🔑 API Key: {api_key[:5]}...{api_key[-5:]}\n\n"
        
        # Balance check
        balance = trader.check_wallet_balance()
        test_message += f"💰 USDT Balance: {balance}\n"
        
        # Trading symbol check
        symbol = os.getenv('TRADE_SYMBOL', 'MNTUSDT')
        test_message += f"🎯 Trading Symbol: {symbol}\n"
        
        # Market data check
        ticker = trader.session.get_tickers(
            category="linear",
            symbol=symbol
        )
        
        if ticker and ticker.get('result'):
            current_price = ticker['result']['list'][0]['lastPrice']
            test_message += f"💵 Current Price: {current_price}\n"
            test_message += "✅ Market data available\n"
        
        # Result message
        test_message += "\n✅ Bybit API connection successful!"
        telegram.send_message(test_message)
        
        logger.info("Bybit API test successful")
        return True
        
    except Exception as e:
        error_msg = f"Bybit API test error: {str(e)}"
        logger.error(error_msg)
        telegram = TelegramBot()
        telegram.send_error_alert(error_msg)
        return False

if __name__ == "__main__":
    test_bybit_connection() 