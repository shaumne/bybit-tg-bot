from modules.announcements import LaunchpoolAnnouncements
from modules.trade import TradeExecutor
from modules.telegram_bot import TelegramBot
from utils.logger import setup_logger
import time

logger = setup_logger('test')

def test_telegram():
    """Test Telegram bağlantısı"""
    try:
        telegram = TelegramBot()
        test_message = "🧪 <b>Test: Telegram Bağlantısı</b>\n✅ Başarılı"
        result = telegram.send_message(test_message)
        assert result == True, "Telegram mesaj gönderimi başarısız"
        logger.info("Telegram testi başarılı")
        return True
    except Exception as e:
        logger.error(f"Telegram testi başarısız: {str(e)}")
        return False

def test_announcements():
    """Test duyuru kontrolü"""
    try:
        announcements = LaunchpoolAnnouncements()
        test_message = "🧪 <b>Test: Duyuru Kontrolü</b>"
        
        # Duyuruları kontrol et
        result = announcements.check_new_listings()
        logger.info(f"Son duyuru kontrolü sonucu: {result}")
        
        # Telegram'a bildir
        telegram = TelegramBot()
        if result:
            test_message += f"\n✅ Yeni duyuru bulundu:\n{result.get('title')}"
        else:
            test_message += "\n✅ Duyuru kontrolü çalışıyor (yeni duyuru yok)"
            
        telegram.send_message(test_message)
        return True
    except Exception as e:
        logger.error(f"Duyuru testi başarısız: {str(e)}")
        return False

def test_trade():
    """Test trade işlemleri"""
    try:
        trader = TradeExecutor()
        telegram = TelegramBot()
        
        # Bakiye kontrolü
        balance = trader.check_wallet_balance()
        
        test_message = (
            "🧪 <b>Test: Trade İşlemleri</b>\n"
            f"💰 Bakiye: {balance} USDT\n"
            "✅ Trade sistemi hazır"
        )
        
        telegram.send_message(test_message)
        return True
    except Exception as e:
        logger.error(f"Trade testi başarısız: {str(e)}")
        return False

def run_all_tests():
    """Tüm testleri çalıştır"""
    try:
        logger.info("Test başlıyor...")
        
        # Telegram testi
        if not test_telegram():
            raise Exception("Telegram testi başarısız")
            
        time.sleep(2)  # Mesajlar arası bekleme
        
        # Duyuru testi
        if not test_announcements():
            raise Exception("Duyuru testi başarısız")
            
        time.sleep(2)
        
        # Trade testi
        if not test_trade():
            raise Exception("Trade testi başarısız")
            
        # Final mesaj
        telegram = TelegramBot()
        success_message = (
            "✅ <b>Tüm Testler Başarılı</b>\n\n"
            "1. Telegram Bağlantısı ✅\n"
            "2. Duyuru Kontrolü ✅\n"
            "3. Trade Sistemi ✅\n\n"
            "Bot çalışmaya hazır! 🚀"
        )
        telegram.send_message(success_message)
        
        logger.info("Tüm testler başarıyla tamamlandı")
        
    except Exception as e:
        logger.error(f"Test hatası: {str(e)}")
        telegram = TelegramBot()
        error_message = f"❌ <b>Test Hatası</b>\n\n{str(e)}"
        telegram.send_message(error_message)

if __name__ == "__main__":
    run_all_tests() 