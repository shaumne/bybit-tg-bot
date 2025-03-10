import time
from modules.announcements import LaunchpoolAnnouncements
from modules.trade import TradeExecutor
from modules.telegram_bot import TelegramBot
from utils.logger import setup_logger
from config.settings import settings

logger = setup_logger('main')

def main():
    try:
        logger.info("Starting bot...")
        
        # Initialize components
        announcements = LaunchpoolAnnouncements()
        trader = TradeExecutor()
        
        # Send startup notification
        startup_message = (
            "🤖 <b>Bybit Launchpool Bot Started</b>\n\n"
            "✅ Status: Active\n"
            "📊 Mode: Testnet\n"
            "⚡️ Monitoring: Launchpool Announcements\n"
            "💫 Trading: MNTUSDT\n"
            f"⏱ Check Interval: {settings.CHECK_INTERVAL}s\n\n"
            "Bot is now monitoring for new Launchpool announcements..."
        )
        bot = TelegramBot()
        bot.send_message(startup_message)
        
        retry_count = 0
        
        while True:
            try:
                # Check for new announcements
                new_announcement = announcements.check_new_listings()
                
                if new_announcement:
                    # Send announcement alert
                    bot.send_launchpool_alert(new_announcement)
                    
                    # Execute trade
                    trade_result = trader.execute_trade()
                    
                    if trade_result:
                        # Send trade alert
                        bot.send_trade_alert(
                            trade_type="LONG",
                            symbol=trade_result['symbol'],
                            price=trade_result['price'],
                            quantity=trade_result['quantity'],
                            sl=trade_result['stop_loss'],
                            tp=trade_result['take_profit']
                        )
                    
                time.sleep(settings.CHECK_INTERVAL)
                retry_count = 0
                
            except Exception as e:
                retry_count += 1
                error_msg = f"Error (Attempt {retry_count}/{settings.MAX_RETRIES}): {str(e)}"
                logger.error(error_msg)
                bot.send_error_alert(error_msg)
                
                if retry_count >= settings.MAX_RETRIES:
                    bot.send_message("🔴 Bot stopped due to maximum retry attempts!")
                    break
                    
                time.sleep(settings.RETRY_DELAY)
                
    except Exception as e:
        logger.critical(f"Critical error: {str(e)}")
        bot.send_error_alert(f"Critical error: {str(e)}")
        raise

if __name__ == "__main__":
    bot = TelegramBot()
    bot.run() 