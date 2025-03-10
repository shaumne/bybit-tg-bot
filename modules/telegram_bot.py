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
        
        if not self.bot_token:
            logger.error("Telegram bot token not found in settings!")
            raise ValueError("Telegram bot token not found!")
        
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
        self.app.add_handler(CommandHandler("setpassword", self.set_password_command))
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
            await self.app.bot.send_message(
                chat_id=self.chat_id,
                text="🤖 <b>Bybit Launchpool Bot Started</b>\n\n"
                     "Welcome! Please select an option:",
                reply_markup=self.get_main_menu(),
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
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        if not settings.BOT_PASSWORD:
            await update.message.reply_text(
                "🔐 Bot is not set up yet. Please set a password:\n"
                "/setpassword <your_password>"
            )
            return SETTING_PASSWORD
            
        await update.message.reply_text(
            "🔒 Please enter bot password:"
        )
        return WAITING_PASSWORD

    async def set_password_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /setpassword command"""
        if settings.BOT_PASSWORD:
            await update.message.reply_text("⚠️ Password is already set!")
            return
            
        try:
            password = context.args[0]
            settings.set_password(password)
            await update.message.reply_text(
                "✅ Password set successfully!\n"
                "🔓 Now use /start command to login."
            )
        except IndexError:
            await update.message.reply_text(
                "❌ Please specify a password:\n"
                "/setpassword <your_password>"
            )
        return ConversationHandler.END

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        if not context.user_data.get('authenticated'):
            # Password check
            if settings.verify_password(update.message.text):
                context.user_data['authenticated'] = True
                await update.message.reply_text(
                    "🤖 <b>Main Menu</b>\nSelect an option:",
                    reply_markup=self.get_main_menu(),
                    parse_mode='HTML'
                )
                return SELECTING_ACTION
            else:
                await update.message.reply_text("❌ Wrong password! Try again:")
                return WAITING_PASSWORD
        
        # Handle settings updates
        try:
            if context.user_data.get('state') == SET_QUANTITY:
                value = float(update.message.text)
                if value < 5.0:
                    await update.message.reply_text("❌ Minimum quantity is 5.0 USDT")
                    return SET_QUANTITY
                settings.QUANTITY = value
                context.user_data['state'] = None
                
            elif context.user_data.get('state') == SET_LEVERAGE:
                value = int(float(update.message.text))
                if not 1 <= value <= 100:
                    await update.message.reply_text("❌ Leverage must be between 1 and 100")
                    return SET_LEVERAGE
                self.settings['leverage'] = value
                context.user_data['state'] = None
                
            elif context.user_data.get('state') == SET_SL:
                value = float(update.message.text)
                if not 0 < value < 100:
                    await update.message.reply_text("❌ Stop Loss must be between 0 and 100")
                    return SET_SL
                settings.STOP_LOSS_PCT = value
                context.user_data['state'] = None
                
            elif context.user_data.get('state') == SET_TP:
                value = float(update.message.text)
                if not 0 < value < 100:
                    await update.message.reply_text("❌ Take Profit must be between 0 and 100")
                    return SET_TP
                settings.TAKE_PROFIT_PCT = value
                context.user_data['state'] = None

            if context.user_data.get('state') is None:
                # Save settings
                settings.save_settings()
                
                # Show updated settings
                settings_text = (
                    "✅ Settings updated successfully!\n\n"
                    "📊 <b>Current Settings</b>\n"
                    f"💰 Quantity: {settings.QUANTITY} USDT\n"
                    f"⚡️ Leverage: {self.settings['leverage']}x\n"
                    f"🔻 Stop Loss: {settings.STOP_LOSS_PCT}%\n"
                    f"🔼 Take Profit: {settings.TAKE_PROFIT_PCT}%"
                )
                
                await update.message.reply_text(
                    settings_text,
                    reply_markup=self.get_settings_menu(),
                    parse_mode='HTML'
                )
                return SELECTING_ACTION
                
        except ValueError:
            await update.message.reply_text(
                "❌ Please enter a valid number"
            )
            return context.user_data.get('state')
                
        return SELECTING_ACTION

    async def menu_actions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle menu button actions"""
        if not context.user_data.get('authenticated'):
            await update.callback_query.answer("⚠️ Please login first!")
            return WAITING_PASSWORD
            
        query = update.callback_query
        await query.answer()
        
        if query.data == 'test_announcement':
            # Execute trade
            trader = TradeExecutor()
            try:
                trade_result = trader.execute_trade(
                    side="Buy",
                    quantity=self.settings['quantity'],
                    sl_percentage=self.settings['stop_loss'],
                    tp_percentage=self.settings['take_profit'],
                    leverage=self.settings['leverage'],
                    category="linear"  # Bybit API için gerekli
                )
                
                if trade_result:
                    await query.message.reply_text(
                        "✅ <b>Trade Executed Successfully!</b>\n\n"
                        f"💹 <b>Entry Price:</b> {trade_result['price']}\n"
                        f"📊 <b>Quantity:</b> {trade_result['quantity']} MNT\n"
                        f"🔻 <b>Stop Loss:</b> {trade_result['stop_loss']}\n"
                        f"🔼 <b>Take Profit:</b> {trade_result['take_profit']}\n"
                        "➖➖➖➖➖➖➖➖➖➖\n"
                        "⚠️ <i>Monitor your position in Bybit!</i>",
                        parse_mode='HTML'
                    )
            except Exception as e:
                await query.message.reply_text(
                    "❌ <b>Trade Execution Failed!</b>\n\n"
                    f"Error: {str(e)}\n\n"
                    "Please check your settings and try again.",
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
                    f"• Quantity: {self.settings['quantity']}\n"
                    f"• Stop Loss: {self.settings['stop_loss']}%\n"
                    f"• Take Profit: {self.settings['take_profit']}%\n"
                    f"• Leverage: {self.settings['leverage']}x\n\n"
                    "🚀 Opening LONG position..."
                )
                
                # Send formatted announcement
                await self.send_message(message)
                
                # Execute trade
                trader = TradeExecutor()
                try:
                    trade_result = trader.execute_trade(
                        side="Buy",
                        quantity=self.settings['quantity'],
                        sl_percentage=self.settings['stop_loss'],
                        tp_percentage=self.settings['take_profit'],
                        leverage=self.settings['leverage']
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
                        await self.send_message(trade_message)
                        
                except Exception as e:
                    error_message = (
                        "❌ <b>Trade Execution Failed!</b>\n\n"
                        f"Error: {str(e)}\n\n"
                        "Please check your settings and try again."
                    )
                    await self.send_message(error_message)
                    
        except Exception as e:
            logger.error(f"Announcement check error: {str(e)}")
            await self.send_message(
                f"⚠️ <b>Announcement Check Error:</b>\n{str(e)}"
            )

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