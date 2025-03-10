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

class TelegramBot:
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not self.bot_token or not self.chat_id:
            logger.error("Telegram credentials not found in .env!")
            raise ValueError("Telegram credentials not found!")
        
        # Initialize settings with defaults
        self.settings = {
            'min_value': 5.0,
            'quantity': 10.0,
            'stop_loss': 2.0,
            'take_profit': 4.0,
            'leverage': 1
        }
        
        # Initialize bot application
        self.app = Application.builder().token(self.bot_token).build()
        
        # Initialize announcements checker
        self.announcements = LaunchpoolAnnouncements()
        
        # Add handlers
        self.app.add_handler(CommandHandler("start", self.check_chat(self.start_command)))
        self.app.add_handler(CommandHandler("settings", self.check_chat(self.show_settings)))
        self.app.add_handler(CallbackQueryHandler(self.check_chat(self.menu_actions)))
        
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
                InlineKeyboardButton("💵 Min Value", callback_data='set_min_value'),
                InlineKeyboardButton("📈 Quantity", callback_data='set_quantity')
            ],
            [
                InlineKeyboardButton("🔻 Stop Loss", callback_data='set_sl'),
                InlineKeyboardButton("🔼 Take Profit", callback_data='set_tp')
            ],
            [
                InlineKeyboardButton("⚡️ Leverage", callback_data='set_leverage'),
                InlineKeyboardButton("🔙 Back", callback_data='back_main')
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        await update.message.reply_text(
            "🤖 <b>Main Menu</b>\nSelect an option:",
            reply_markup=self.get_main_menu(),
            parse_mode='HTML'
        )

    async def menu_actions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle menu button actions"""
        query = update.callback_query
        await query.answer()
        
        logger.info(f"Button pressed: {query.data}")
        
        if query.data == 'settings':
            await query.message.edit_text(
                "⚙️ <b>Settings Menu</b>\nSelect a setting to modify:",
                reply_markup=self.get_settings_menu(),
                parse_mode=ParseMode.HTML
            )
            
        elif query.data == 'test_announcement':
            # Send test announcement message
            test_message = (
                "🔥 <b>Test Announcement!</b> 🔥\n\n"
                "📌 <b>Title:</b>\n"
                "Bybit Launchpool: New MNT Token Mining Event\n\n"
                "📝 <b>Description:</b>\n"
                "Bybit is excited to announce the launch of MNT Token Mining Event. "
                "Users can now stake BIT to earn MNT tokens.\n\n"
                f"⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                "🔗 <b>Link:</b> https://announcements.bybit.com/\n\n"
                "➖➖➖➖➖➖➖➖➖➖\n"
                "🤖 <b>Bot Action:</b>\n"
                f"• Symbol: MNTUSDT\n"
                f"• Quantity: {self.settings['quantity']}\n"
                f"• Stop Loss: {self.settings['stop_loss']}%\n"
                f"• Take Profit: {self.settings['take_profit']}%\n"
                f"• Leverage: {self.settings['leverage']}x\n\n"
                "🚀 Opening LONG position..."
            )
            
            await self.send_message(test_message)
            
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
            
        elif query.data == 'show_settings':
            settings_text = (
                "📊 <b>Current Settings</b>\n\n"
                f"💵 Min Value: {self.settings['min_value']} USDT\n"
                f"📈 Quantity: {self.settings['quantity']}\n"
                f"🔻 Stop Loss: {self.settings['stop_loss']}%\n"
                f"🔼 Take Profit: {self.settings['take_profit']}%\n"
                f"⚡️ Leverage: {self.settings['leverage']}x"
            )
            await query.message.edit_text(
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
    
    async def set_min_value(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set minimum value"""
        try:
            value = float(update.message.text)
            if value < 5:
                await update.message.reply_text(
                    "❌ Minimum value must be at least 5 USDT\n"
                    "Please try again:"
                )
                return SET_MIN_VALUE
            
            self.settings['min_value'] = value
            await update.message.reply_text(
                f"✅ Minimum value set to {value} USDT",
                reply_markup=self.get_settings_menu()
            )
            return SELECTING_ACTION
            
        except ValueError:
            await update.message.reply_text(
                "❌ Please enter a valid number\n"
                "Try again:"
            )
            return SET_MIN_VALUE
    
    # Similar handlers for quantity, stop loss, take profit, and leverage
    async def set_quantity(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set quantity"""
        try:
            value = float(update.message.text)
            self.settings['quantity'] = value
            await update.message.reply_text(
                f"✅ Quantity set to {value}",
                reply_markup=self.get_settings_menu()
            )
            return SELECTING_ACTION
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number")
            return SET_QUANTITY
    
    async def set_sl(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set stop loss percentage"""
        try:
            value = float(update.message.text)
            if value <= 0 or value >= 100:
                await update.message.reply_text("❌ Please enter a value between 0 and 100")
                return SET_SL
            self.settings['stop_loss'] = value
            await update.message.reply_text(
                f"✅ Stop Loss set to {value}%",
                reply_markup=self.get_settings_menu()
            )
            return SELECTING_ACTION
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number")
            return SET_SL
    
    async def set_tp(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set take profit percentage"""
        try:
            value = float(update.message.text)
            if value <= 0 or value >= 100:
                await update.message.reply_text("❌ Please enter a value between 0 and 100")
                return SET_TP
            self.settings['take_profit'] = value
            await update.message.reply_text(
                f"✅ Take Profit set to {value}%",
                reply_markup=self.get_settings_menu()
            )
            return SELECTING_ACTION
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number")
            return SET_TP
    
    async def set_leverage(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set leverage"""
        try:
            value = int(update.message.text)
            if value < 1 or value > 100:
                await update.message.reply_text("❌ Please enter a value between 1 and 100")
                return SET_LEVERAGE
            self.settings['leverage'] = value
            await update.message.reply_text(
                f"✅ Leverage set to {value}x",
                reply_markup=self.get_settings_menu()
            )
            return SELECTING_ACTION
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number")
            return SET_LEVERAGE
    
    async def show_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current settings"""
        settings_text = (
            "📊 <b>Current Settings</b>\n\n"
            f"💵 Min Value: {self.settings['min_value']} USDT\n"
            f"📈 Quantity: {self.settings['quantity']}\n"
            f"🔻 Stop Loss: {self.settings['stop_loss']}%\n"
            f"🔼 Take Profit: {self.settings['take_profit']}%\n"
            f"⚡️ Leverage: {self.settings['leverage']}x"
        )
        await update.message.reply_text(
            settings_text,
            reply_markup=self.get_main_menu(),
            parse_mode='HTML'
        )
        return SELECTING_ACTION
    
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