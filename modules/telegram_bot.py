from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)
import requests
import os
from utils.logger import setup_logger
from dotenv import load_dotenv

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
        
        # Add handlers
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.start_command)],
            states={
                SELECTING_ACTION: [
                    CallbackQueryHandler(self.menu_actions)
                ],
                SET_MIN_VALUE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.set_min_value)
                ],
                SET_QUANTITY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.set_quantity)
                ],
                SET_SL: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.set_sl)
                ],
                SET_TP: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.set_tp)
                ],
                SET_LEVERAGE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.set_leverage)
                ]
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        
        self.app.add_handler(conv_handler)
        self.app.add_handler(CommandHandler("settings", self.show_settings))
        
        # Start bot
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)
    
    def get_main_menu(self):
        """Get main menu keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("⚙️ Settings", callback_data='settings'),
                InlineKeyboardButton("💰 Trade", callback_data='trade_menu')
            ],
            [
                InlineKeyboardButton("📊 Current Settings", callback_data='show_settings'),
                InlineKeyboardButton("❌ Cancel", callback_data='cancel')
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
    
    def get_trade_menu(self):
        """Get trade menu keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("🟢 LONG", callback_data='trade_long'),
                InlineKeyboardButton("🔴 SHORT", callback_data='trade_short')
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data='back_main')
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send start message with main menu"""
        await update.message.reply_text(
            "🤖 <b>Bybit Launchpool Bot</b>\n\n"
            "Welcome! Please select an option:",
            reply_markup=self.get_main_menu(),
            parse_mode='HTML'
        )
        return SELECTING_ACTION
    
    async def menu_actions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle menu actions"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'settings':
            await query.message.edit_text(
                "⚙️ <b>Settings Menu</b>\n\n"
                "Please select a setting to modify:",
                reply_markup=self.get_settings_menu(),
                parse_mode='HTML'
            )
            return SELECTING_ACTION
            
        elif query.data == 'trade_menu':
            await query.message.edit_text(
                "💰 <b>Trade Menu</b>\n\n"
                "Select trade direction:",
                reply_markup=self.get_trade_menu(),
                parse_mode='HTML'
            )
            return SELECTING_ACTION
            
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
                parse_mode='HTML'
            )
            return SELECTING_ACTION
            
        elif query.data.startswith('set_'):
            setting = query.data.replace('set_', '')
            await query.message.edit_text(
                f"Please enter new value for {setting.replace('_', ' ').title()}:"
            )
            return globals()[query.data.upper()]
            
        elif query.data == 'back_main':
            await query.message.edit_text(
                "🤖 <b>Main Menu</b>\n\n"
                "Please select an option:",
                reply_markup=self.get_main_menu(),
                parse_mode='HTML'
            )
            return SELECTING_ACTION
            
        elif query.data.startswith('trade_'):
            side = "Buy" if query.data == 'trade_long' else "Sell"
            
            from modules.trade import TradeExecutor
            trader = TradeExecutor()
            
            try:
                trade_result = trader.execute_trade(
                    side=side,
                    quantity=self.settings['quantity'],
                    sl_percentage=self.settings['stop_loss'],
                    tp_percentage=self.settings['take_profit'],
                    leverage=self.settings['leverage']
                )
                
                if trade_result:
                    await self.send_trade_alert(
                        trade_type="LONG" if side == "Buy" else "SHORT",
                        symbol=trade_result['symbol'],
                        price=trade_result['price'],
                        quantity=trade_result['quantity'],
                        sl=trade_result['stop_loss'],
                        tp=trade_result['take_profit']
                    )
            except Exception as e:
                await self.send_error_alert(f"Trade execution error: {str(e)}")
            
            return SELECTING_ACTION
    
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
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel conversation"""
        await update.message.reply_text(
            "Operation cancelled.",
            reply_markup=self.get_main_menu()
        )
        return SELECTING_ACTION
    
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
                parse_mode=parse_mode
            )
            return True
        except Exception as e:
            logger.error(f"Telegram error: {str(e)}")
            return False
    
    async def send_trade_alert(self, trade_type, symbol, price, quantity, sl, tp):
        """Send trade alert message"""
        message = (
            f"🚨 <b>New Trade Alert</b> 🚨\n\n"
            f"Type: {trade_type}\n"
            f"Symbol: {symbol}\n"
            f"Price: {price}\n"
            f"Quantity: {quantity}\n"
            f"Stop Loss: {sl}\n"
            f"Take Profit: {tp}\n"
        )
        return await self.send_message(message)
    
    async def send_error_alert(self, error_message):
        """Send error alert"""
        message = (
            f"⚠️ <b>Error Alert</b> ⚠️\n\n"
            f"Error: {error_message}"
        )
        return await self.send_message(message)

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