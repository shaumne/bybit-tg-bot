from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from telegram.ext import JobQueue
import requests
import os
from utils.logger import setup_logger
from dotenv import load_dotenv
import asyncio
from modules.trade import TradeExecutor
from modules.announcements import LaunchpoolAnnouncements
from datetime import datetime
from config.settings import settings
import json

logger = setup_logger('telegram')

# Load .env
load_dotenv()

# States for conversation
SELECTING_ACTION = 0
SET_MIN_VALUE = 1
SET_QUANTITY = 2
SET_SL = 3
SET_TP = 4
SET_LEVERAGE = 5
WAITING_PASSWORD = 6
SETTING_PASSWORD = 7

class TelegramBot:
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.user_settings = self.load_user_settings()
        
        if not self.bot_token or not self.chat_id:
            logger.error("Telegram bot token or chat ID not found in settings!")
            raise ValueError("Telegram bot token or chat ID not found!")
        
        # Initialize settings with defaults
        self.settings = {
            'min_value': 5.0,
            'quantity': settings.QUANTITY,
            'stop_loss': settings.STOP_LOSS_PCT,
            'take_profit': settings.TAKE_PROFIT_PCT,
            'leverage': 1
        }
        
        # Initialize bot application
        self.app = Application.builder().token(self.bot_token).build()
        
        # Initialize announcements checker
        self.announcements = LaunchpoolAnnouncements()
        
        # Add handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.app.add_handler(CallbackQueryHandler(self.menu_actions))
        
        # Post init setup
        self.app.post_init = self.post_init
        self.app.post_shutdown = self.post_shutdown
        
        # Add announcement check job
        self.app.job_queue.run_repeating(
            self.check_announcements,
            interval=30,  # Her 30 saniyede bir kontrol et
            first=5  # İlk kontrolü 5 saniye sonra başlat
        )

        # Add position monitoring job
        self.app.job_queue.run_repeating(
            self.check_position_status,
            interval=60,  # Her 1 dakikada bir kontrol
            first=5      # İlk kontrol 5 saniye sonra
        )

    async def post_init(self, application: Application) -> None:
        """Post initialization hook"""
        await self.send_initial_menu()

    async def post_shutdown(self, application: Application) -> None:
        """Post shutdown hook"""
        logger.info("Bot shutting down...")

    def run(self):
        """Run the bot"""
        logger.info("Starting bot...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)

    async def send_initial_menu(self):
        """Send initial menu when bot starts"""
        try:
            user = await self.app.bot.get_chat(self.chat_id)
            username = user.username or "User"
            
            if 'password' not in self.user_settings:
                welcome_message = (
                    f"👋 Welcome {username}!\n\n"
                    "🤖 <b>Bybit Launchpool Bot</b>\n\n"
                    "ℹ️ Initial Setup Required:\n"
                    "1. Please use /start command\n"
                    "2. Set a password to secure your bot\n"
                    "3. Password must be at least 4 characters\n\n"
                    "🔒 Security Info:\n"
                    f"• Chat ID: {self.chat_id}\n"
                    "• Access: Authorized\n"
                    "• Status: Waiting for password setup\n\n"
                    "⚠️ Please set your password to continue!"
                )
            else:
                welcome_message = (
                    f"👋 Welcome back {username}!\n\n"
                    "🤖 <b>Bybit Launchpool Bot</b>\n\n"
                    "🔒 Security Info:\n"
                    f"• Chat ID: {self.chat_id}\n"
                    "• Access: Authorized\n"
                    "• Status: Password protected\n\n"
                    "Please use /start to login."
                )
                
            await self.app.bot.send_message(
                chat_id=self.chat_id,
                text=welcome_message,
                parse_mode='HTML'
            )
            logger.info("Initial menu sent successfully")
            
        except Exception as e:
            logger.error(f"Error sending initial menu: {str(e)}")
    
    def check_chat(self, func):
        """Decorator to check if the message is from allowed chat"""
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if not update.effective_chat:
                return
                
            chat_id = str(update.effective_chat.id)
            
            # Check if message is from allowed chat
            if chat_id != str(self.chat_id):
                logger.warning(f"Unauthorized chat access attempt - Chat: {chat_id}")
                try:
                    await update.effective_message.reply_text(
                        "⚠️ This bot is not available in this chat."
                    )
                except Exception:
                    pass
                return ConversationHandler.END
            
            return await func(update, context)
        return wrapper
    
    def get_main_menu(self):
        """Get main menu keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("⚙️ Settings", callback_data='settings'),
                InlineKeyboardButton("🚀 Test Announcement", callback_data='test_announcement')
            ],
            [
                InlineKeyboardButton("📊 Current Settings", callback_data='show_settings')
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_settings_menu(self):
        """Get settings menu keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("📊 Quantity", callback_data='set_quantity'),
                InlineKeyboardButton("⚡️ Leverage", callback_data='set_leverage')
            ],
            [
                InlineKeyboardButton("🔻 Stop Loss", callback_data='set_sl'),
                InlineKeyboardButton("🔼 Take Profit", callback_data='set_tp')
            ],
            [
                InlineKeyboardButton("🔙 Back to Main Menu", callback_data='back_main')
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def load_user_settings(self):
        """Load user settings from JSON"""
        try:
            with open('config/user_settings.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}  # Boş settings döndür
        except Exception as e:
            logger.error(f"Error loading user settings: {str(e)}")
            return {}

    def save_user_settings(self, settings):
        """Save user settings to JSON"""
        try:
            os.makedirs('config', exist_ok=True)
            with open('config/user_settings.json', 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving user settings: {str(e)}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        # Chat ID kontrolü
        if str(update.effective_chat.id) != str(self.chat_id):
            await update.message.reply_text("⛔️ Unauthorized access!")
            return

        # Şifre kontrolü
        if 'password' not in self.user_settings:
            await update.message.reply_text(
                "👋 Welcome to Bybit Launchpool Bot!\n\n"
                "Please set a password to secure your bot.\n"
                "The password must be at least 4 characters long:"
            )
            context.user_data['state'] = SETTING_PASSWORD
            return SETTING_PASSWORD
        else:
            await update.message.reply_text(
                "👋 Welcome to Bybit Launchpool Bot!\n\n"
                "Please enter your password to continue:"
            )
            return WAITING_PASSWORD

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        # Chat ID kontrolü
        if str(update.effective_chat.id) != str(self.chat_id):
            await update.message.reply_text("⛔️ Unauthorized access!")
            return

        state = context.user_data.get('state')

        # İlk şifre belirleme
        if state == SETTING_PASSWORD:
            if len(update.message.text) < 4:
                await update.message.reply_text(
                    "❌ Password must be at least 4 characters long.\n"
                    "Please try again:"
                )
                return SETTING_PASSWORD
                
            self.user_settings['password'] = update.message.text
            self.save_user_settings(self.user_settings)
            
            await update.message.reply_text(
                "✅ Password set successfully!\n\n"
                "Please login with your new password:"
            )
            context.user_data['state'] = WAITING_PASSWORD
            return WAITING_PASSWORD

        # Normal şifre kontrolü
        if not context.user_data.get('authenticated'):
            if update.message.text == self.user_settings.get('password'):
                context.user_data['authenticated'] = True
                await update.message.reply_text(
                    "🔓 Login successful!\n\n"
                    "Select an option:",
                    reply_markup=self.get_main_menu()
                )
                return SELECTING_ACTION
            else:
                await update.message.reply_text("❌ Wrong password! Try again:")
                return WAITING_PASSWORD

        # Eğer authenticate olmuşsa, state'e göre işlem yap
        try:
            if state == SET_QUANTITY:
                quantity = float(update.message.text)
                if quantity <= 0:
                    raise ValueError("Quantity must be positive")
                    
                settings.QUANTITY = quantity
                settings.save_settings()
                self.settings['quantity'] = quantity
                
                await update.message.reply_text(
                    f"✅ Quantity updated to: {quantity} USDT\n\n"
                    "Select an option:",
                    reply_markup=self.get_settings_menu()
                )
                
            elif state == SET_SL:
                sl = float(update.message.text)
                if not 0 <= sl <= 100:
                    raise ValueError("Stop Loss must be between 0-100")
                    
                settings.STOP_LOSS_PCT = sl
                settings.save_settings()
                self.settings['stop_loss'] = sl
                
                await update.message.reply_text(
                    f"✅ Stop Loss updated to: {sl}%\n\n"
                    "Select an option:",
                    reply_markup=self.get_settings_menu()
                )
                
            elif state == SET_TP:
                tp = float(update.message.text)
                if not 0 <= tp <= 100:
                    raise ValueError("Take Profit must be between 0-100")
                    
                settings.TAKE_PROFIT_PCT = tp
                settings.save_settings()
                self.settings['take_profit'] = tp
                
                await update.message.reply_text(
                    f"✅ Take Profit updated to: {tp}%\n\n"
                    "Select an option:",
                    reply_markup=self.get_settings_menu()
                )
                
            elif state == SET_LEVERAGE:
                leverage = int(update.message.text)
                if not 1 <= leverage <= 100:
                    raise ValueError("Leverage must be between 1-100")
                    
                self.settings['leverage'] = leverage
                settings.save_settings()
                
                await update.message.reply_text(
                    f"✅ Leverage updated to: {leverage}x\n\n"
                    "Select an option:",
                    reply_markup=self.get_settings_menu()
                )
                
        except ValueError as e:
            await update.message.reply_text(
                f"❌ Invalid value: {str(e)}\n"
                "Please try again:"
            )
            return state
            
        context.user_data['state'] = SELECTING_ACTION
        return SELECTING_ACTION

    async def menu_actions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle menu button actions"""
        if not context.user_data.get('authenticated'):
            await update.callback_query.answer("⚠️ Please login first!")
            return WAITING_PASSWORD
            
        query = update.callback_query
        await query.answer()
        
        if query.data == 'test_announcement':
            # Simüle edilmiş duyuru mesajı
            test_announcement = {
                'title': 'Test: New MNT Launchpool!',
                'description': 'This is a test announcement to simulate real launchpool behavior.',
                'dateTimestamp': str(int(datetime.now().timestamp() * 1000)),
                'url': 'https://www.bybit.com/announcements'
            }
            
            # Format announcement time
            timestamp = int(test_announcement.get('dateTimestamp', 0)) / 1000
            date_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            
            # Format announcement message
            message = (
                "🔥 <b>New Launchpool Announcement!</b> 🔥\n\n"
                f"📌 <b>Title:</b>\n{test_announcement['title']}\n\n"
                f"📝 <b>Description:</b>\n{test_announcement['description']}\n\n"
                f"⏰ <b>Time:</b> {date_time}\n"
                f"🔗 <b>Link:</b> {test_announcement['url']}\n\n"
                "➖➖➖➖➖➖➖➖➖➖\n"
                "🤖 <b>Bot Action:</b>\n"
                f"• Symbol: MNTUSDT\n"
                f"• Quantity: {settings.QUANTITY}\n"
                f"• Stop Loss: {settings.STOP_LOSS_PCT}%\n"
                f"• Take Profit: {settings.TAKE_PROFIT_PCT}%\n"
                f"• Leverage: {self.settings['leverage']}x\n\n"
                "🚀 Opening LONG position..."
            )
            
            # Send announcement message
            await query.message.reply_text(
                message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            
            # Execute trade
            trader = TradeExecutor()
            try:
                trade_result = trader.execute_trade(
                    side="Buy",
                    quantity=settings.QUANTITY,
                    sl_percentage=settings.STOP_LOSS_PCT,
                    tp_percentage=settings.TAKE_PROFIT_PCT,
                    leverage=self.settings['leverage'],
                    category="linear"
                )
                
                if trade_result:
                    trade_message = (
                        "✅ <b>Trade Executed Successfully!</b>\n\n"
                        f"💹 <b>Entry Price:</b> {trade_result['price']}\n"
                        f"📊 <b>Quantity:</b> {trade_result['quantity']} MNT\n"
                        f"🔻 <b>Stop Loss:</b> {trade_result['stop_loss']}\n"
                        f"🔼 <b>Take Profit:</b> {trade_result['take_profit']}\n"
                        "➖➖➖➖➖➖➖➖➖➖\n"
                        "⚠️ <i>Monitor your position in Bybit!</i>"
                    )
                    
                    await query.message.reply_text(
                        trade_message,
                        parse_mode='HTML'
                    )
                    
                    # Start position monitoring
                    context.job_queue.run_repeating(
                        self.check_position_status,
                        interval=60,  # Her 1 dakikada bir kontrol
                        first=10,    # İlk kontrol 10 saniye sonra
                        data=trade_result.get('orderId'),
                        name=f"position_monitor_{trade_result.get('orderId')}"
                    )
                    
                    await query.message.reply_text(
                        "📊 Position monitoring started!\n"
                        "You will receive updates every minute.",
                        parse_mode='HTML'
                    )

            except Exception as e:
                error_message = (
                    "❌ <b>Trade Execution Failed!</b>\n\n"
                    f"Error: {str(e)}\n\n"
                    "Please check your settings and try again."
                )
                
                await query.message.reply_text(
                    error_message,
                    parse_mode='HTML'
                )
        
        elif query.data == 'settings':
            # Send new message instead of editing
            await query.message.reply_text(
                "⚙️ <b>Settings Menu</b>\n"
                "Select a setting to modify:",
                reply_markup=self.get_settings_menu(),
                parse_mode=ParseMode.HTML
            )
        
        elif query.data == 'set_quantity':
            context.user_data['state'] = SET_QUANTITY
            await query.message.reply_text(
                f"📊 Current quantity: {settings.QUANTITY} USDT\n"
                "Enter new quantity (minimum 5.0):"
            )
            return SET_QUANTITY
            
        elif query.data == 'set_leverage':
            context.user_data['state'] = SET_LEVERAGE
            await query.message.reply_text(
                f"⚡️ Current leverage: {self.settings['leverage']}x\n"
                "Enter new leverage (1-100):"
            )
            return SET_LEVERAGE
            
        elif query.data == 'set_sl':
            context.user_data['state'] = SET_SL
            await query.message.reply_text(
                f"🔻 Current Stop Loss: {settings.STOP_LOSS_PCT}%\n"
                "Enter new Stop Loss percentage (0-100):"
            )
            return SET_SL
            
        elif query.data == 'set_tp':
            context.user_data['state'] = SET_TP
            await query.message.reply_text(
                f"🔼 Current Take Profit: {settings.TAKE_PROFIT_PCT}%\n"
                "Enter new Take Profit percentage (0-100):"
            )
            return SET_TP

        elif query.data == 'show_settings':
            settings_text = (
                "📊 <b>Current Settings</b>\n\n"
                f"💰 Quantity: {settings.QUANTITY} USDT\n"
                f"⚡️ Leverage: {self.settings['leverage']}x\n"
                f"🔻 Stop Loss: {settings.STOP_LOSS_PCT}%\n"
                f"🔼 Take Profit: {settings.TAKE_PROFIT_PCT}%\n"
            )
            await query.message.reply_text(
                settings_text,
                reply_markup=self.get_main_menu(),
                parse_mode=ParseMode.HTML
            )
            
        elif query.data == 'back_main':
            await query.message.edit_text(
                "🤖 <b>Main Menu</b>\nSelect an option:",
                reply_markup=self.get_main_menu(),
                parse_mode=ParseMode.HTML
            )
    
    async def send_message(self, message, parse_mode='HTML'):
        """Send message to Telegram"""
        try:
            await self.app.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode,
                disable_web_page_preview=True
            )
            return True
        except Exception as e:
            logger.error(f"Telegram error: {str(e)}")
            return False
    
    async def send_trade_alert(self, trade_type, symbol, price, quantity, sl, tp):
        """Send trade alert message"""
        message = (
            "🚨 <b>New Trade Alert</b> 🚨\n\n"
            f"Type: {trade_type}\n"
            f"Symbol: {symbol}\n"
            f"Price: {price}\n"
            f"Quantity: {quantity}\n"
            f"Stop Loss: {sl}\n"
            f"Take Profit: {tp}"
        )
        await self.send_message(message)
    
    async def send_error_alert(self, error_message):
        """Send error alert message"""
        message = (
            "⚠️ <b>Error Alert</b> ⚠️\n\n"
            f"{error_message}"
        )
        await self.send_message(message)

    async def check_announcements(self, context: ContextTypes.DEFAULT_TYPE):
        """Check for new Launchpool announcements"""
        try:
            announcement = self.announcements.check_new_listings()
            
            if announcement:
                # Format announcement time
                timestamp = int(announcement.get('dateTimestamp', 0)) / 1000
                date_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                
                # Get announcement details
                title = announcement.get('title', 'No Title')
                description = announcement.get('description', 'No Description')
                link = announcement.get('url', '#')
                
                # Format message
                message = (
                    "🔥 <b>New Launchpool Announcement!</b> 🔥\n\n"
                    f"📌 <b>Title:</b>\n{title}\n\n"
                    f"📝 <b>Description:</b>\n{description}\n\n"
                    f"⏰ <b>Time:</b> {date_time}\n"
                    f"🔗 <b>Link:</b> {link}\n\n"
                    "➖➖➖➖➖➖➖➖➖➖\n"
                    "🤖 <b>Bot Action:</b>\n"
                    f"• Symbol: MNTUSDT\n"
                    f"• Quantity: {settings.QUANTITY}\n"
                    f"• Stop Loss: {settings.STOP_LOSS_PCT}%\n"
                    f"• Take Profit: {settings.TAKE_PROFIT_PCT}%\n"
                    f"• Leverage: {self.settings['leverage']}x\n\n"
                    "🚀 Opening LONG position..."
                )
                
                # Send announcement to all chats
                for chat_id in context.bot_data.get('authorized_chats', [update.effective_chat.id]):
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode='HTML',
                        disable_web_page_preview=True
                    )
                
                # Execute trade
                trader = TradeExecutor()
                try:
                    trade_result = trader.execute_trade(
                        side="Buy",
                        quantity=settings.QUANTITY,
                        sl_percentage=settings.STOP_LOSS_PCT,
                        tp_percentage=settings.TAKE_PROFIT_PCT,
                        leverage=self.settings['leverage'],
                        category="linear"
                    )
                    
                    if trade_result:
                        trade_message = (
                            "✅ <b>Trade Executed Successfully!</b>\n\n"
                            f"💹 <b>Entry Price:</b> {trade_result['price']}\n"
                            f"📊 <b>Quantity:</b> {trade_result['quantity']} MNT\n"
                            f"🔻 <b>Stop Loss:</b> {trade_result['stop_loss']}\n"
                            f"🔼 <b>Take Profit:</b> {trade_result['take_profit']}\n"
                            "➖➖➖➖➖➖➖➖➖➖\n"
                            "⚠️ <i>Monitor your position in Bybit!</i>"
                        )
                        
                        for chat_id in context.bot_data.get('authorized_chats', [update.effective_chat.id]):
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=trade_message,
                                parse_mode='HTML'
                            )
                        
                except Exception as e:
                    error_message = (
                        "❌ <b>Trade Execution Failed!</b>\n\n"
                        f"Error: {str(e)}\n\n"
                        "Please check your settings and try again."
                    )
                    
                    for chat_id in context.bot_data.get('authorized_chats', [update.effective_chat.id]):
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=error_message,
                            parse_mode='HTML'
                        )
                    
        except Exception as e:
            logger.error(f"Announcement check error: {str(e)}")
            error_message = f"⚠️ <b>Announcement Check Error:</b>\n{str(e)}"
            
            for chat_id in context.bot_data.get('authorized_chats', [update.effective_chat.id]):
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=error_message,
                    parse_mode='HTML'
                )

    async def check_position_status(self, context: ContextTypes.DEFAULT_TYPE, order_id=None):
        """Check position status and send updates"""
        try:
            trader = TradeExecutor()
            position = trader.get_position_info()
            
            if position:
                # Pozisyon bilgilerini al
                entry_price = float(position.get('entryPrice', 0))
                current_price = float(position.get('markPrice', 0))
                size = float(position.get('size', 0))
                unrealized_pnl = float(position.get('unrealisedPnl', 0))
                
                # PNL yüzdesini hesapla
                pnl_percentage = (unrealized_pnl / (entry_price * size)) * 100
                
                # Pozisyon durumu mesajı
                status_message = (
                    "📊 <b>Position Update</b>\n\n"
                    f"💰 Entry Price: {entry_price:.4f}\n"
                    f"📈 Current Price: {current_price:.4f}\n"
                    f"📊 Position Size: {size}\n"
                    f"💵 Unrealized PNL: {unrealized_pnl:.2f} USDT\n"
                    f"📈 PNL %: {pnl_percentage:.2f}%\n\n"
                )
                
                # Pozisyon durumuna göre emoji ekle
                if pnl_percentage > 0:
                    status_message += "🟢 In Profit"
                elif pnl_percentage < 0:
                    status_message += "🔴 In Loss"
                else:
                    status_message += "⚪️ Break Even"
                
                # Mesajı gönder
                await context.bot.send_message(
                    chat_id=self.chat_id,
                    text=status_message,
                    parse_mode='HTML'
                )
                
                # TP veya SL'ye yakınsa uyarı gönder
                sl_price = entry_price * (1 - settings.STOP_LOSS_PCT / 100)
                tp_price = entry_price * (1 + settings.TAKE_PROFIT_PCT / 100)
                
                if current_price <= sl_price * 1.01:  # SL'ye %1 kaldıysa
                    await context.bot.send_message(
                        chat_id=self.chat_id,
                        text="⚠️ <b>Warning:</b> Price is near Stop Loss!",
                        parse_mode='HTML'
                    )
                elif current_price >= tp_price * 0.99:  # TP'ye %1 kaldıysa
                    await context.bot.send_message(
                        chat_id=self.chat_id,
                        text="🎯 <b>Alert:</b> Price is near Take Profit!",
                        parse_mode='HTML'
                    )
                
                # Pozisyon kapandıysa bildir
                if size == 0 and order_id:
                    closed_position = trader.get_order_history(order_id)
                    if closed_position:
                        realized_pnl = float(closed_position.get('closedPnl', 0))
                        close_message = (
                            "🔒 <b>Position Closed</b>\n\n"
                            f"💰 Realized PNL: {realized_pnl:.2f} USDT\n"
                            f"📈 Final PNL %: {(realized_pnl / (entry_price * size)) * 100:.2f}%"
                        )
                        await context.bot.send_message(
                            chat_id=self.chat_id,
                            text=close_message,
                            parse_mode='HTML'
                        )
                
            else:
                logger.warning("No active position found")
                
        except Exception as e:
            logger.error(f"Error checking position: {str(e)}")

def run_bot():
    """Run the bot"""
    bot = TelegramBot()
    asyncio.run(bot.run())

# Test message
bot = TelegramBot()
print(f"Using chat_id: {os.getenv('TELEGRAM_CHAT_ID')}")
test_message = (
    "🤖 <b>Bot Test Message</b>\n\n"
    "Channel ID: -1002404132090\n"
    "Status: Connected\n"
    "Time: Running"
)
bot.send_message(test_message) 