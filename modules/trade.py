from pybit.unified_trading import HTTP
import os
from utils.logger import setup_logger
from dotenv import load_dotenv
from config.settings import settings
import time
import math
import sys

# Load .env
load_dotenv()

# Configure logger
logger = setup_logger('trade')

class TradeExecutor:
    def __init__(self):
        """Initialize TradeExecutor"""
        try:
            self.client = HTTP(
                testnet=settings.TESTNET,
                api_key=settings.API_KEY,
                api_secret=settings.API_SECRET
            )
            self.symbol = settings.SYMBOL
            
            logger.info("TradeExecutor initialized. Testnet: %s", settings.TESTNET)
            
        except Exception as e:
            logger.error("TradeExecutor initialization error: %s", str(e))
            raise
            
    def get_min_trading_qty(self):
        """Get minimum trading quantity for symbol"""
        try:
            instruments = self.client.get_instruments_info(
                category="linear",
                symbol=self.symbol
            )
            
            if instruments and instruments.get('result'):
                min_qty = float(instruments['result']['list'][0]['lotSizeFilter']['minOrderQty'])
                logger.info(f"Minimum trading quantity for {self.symbol}: {min_qty}")
                return min_qty
            return 1.0
            
        except Exception as e:
            logger.error(f"Error getting min trading qty: {str(e)}")
            return 1.0
            
    def check_wallet_balance(self):
        """Check wallet USDT balance"""
        try:
            wallet_info = self.client.get_wallet_balance(
                accountType="UNIFIED",
                coin="USDT"
            )
            
            if wallet_info and wallet_info.get('result'):
                balance = wallet_info['result']['list'][0]['totalAvailableBalance']
                logger.info(f"Wallet balance: {balance} USDT")
                return float(balance)
            else:
                logger.error("Could not get wallet balance")
                return 0
                
        except Exception as e:
            logger.error(f"Error checking wallet balance: {str(e)}")
            return 0
            
    def get_lot_size_rules(self):
        """Get lot size rules for the symbol"""
        try:
            instruments = self.client.get_instruments_info(
                category="linear",
                symbol=self.symbol
            )
            
            if instruments and instruments.get('result'):
                instrument = instruments['result']['list'][0]
                lot_size_filter = instrument['lotSizeFilter']
                
                min_qty = float(lot_size_filter['minOrderQty'])
                max_qty = float(lot_size_filter['maxOrderQty'])
                qty_step = float(lot_size_filter['qtyStep'])
                
                logger.info(f"Lot size rules - Min: {min_qty}, Max: {max_qty}, Step: {qty_step}")
                return min_qty, max_qty, qty_step
                
            return 1.0, 10000.0, 1.0
            
        except Exception as e:
            logger.error(f"Error getting lot size rules: {str(e)}")
            return 1.0, 10000.0, 1.0

    def normalize_quantity(self, quantity):
        """Normalize quantity according to lot size rules"""
        min_qty, max_qty, qty_step = self.get_lot_size_rules()
        
        # Ensure quantity is within limits
        quantity = max(min_qty, min(quantity, max_qty))
        
        # Round to nearest step
        steps = round(quantity / qty_step)
        quantity = steps * qty_step
        
        return quantity

    async def execute_trade(self, quantity, stop_loss, take_profit, leverage):
        """Execute trade with given parameters"""
        try:
            # Sembol sabit
            symbol = "MNTUSDT"
            
            # Market fiyatını al
            ticker = self.client.get_tickers(
                category="linear",
                symbol=symbol
            )
            
            if not ticker or ticker.get('retCode') != 0:
                return {'success': False, 'error': 'Could not get market price'}
                
            mark_price = float(ticker['result']['list'][0]['markPrice'])
            
            # Long pozisyon için SL ve TP hesapla
            sl_price = str(round(mark_price * (1 - stop_loss/100), 4))
            tp_price = str(round(mark_price * (1 + take_profit/100), 4))
            
            # Order parametreleri
            order_params = {
                "category": "linear",
                "symbol": symbol,
                "side": "Buy",
                "orderType": "Market",
                "qty": str(quantity),
                "stopLoss": sl_price,
                "takeProfit": tp_price,
                "leverage": str(leverage),
                "positionIdx": 0  # Tek yönlü pozisyon
            }
            
            logger.info(f"Placing order with params: {order_params}")
            logger.info(f"Market price: {mark_price}, SL: {sl_price}, TP: {tp_price}")
            
            # Pozisyon aç
            response = self.client.place_order(**order_params)
            
            if response and response.get('retCode') == 0:
                return {
                    'success': True,
                    'data': {
                        'entry_price': mark_price,
                        'quantity': quantity,
                        'stop_loss': float(sl_price),
                        'take_profit': float(tp_price)
                    }
                }
            else:
                error_msg = response.get('retMsg', 'Unknown error')
                logger.error(f"Trade execution failed: {error_msg}")
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            logger.error(f"Error executing trade: {str(e)}")
            return {'success': False, 'error': str(e)}

    def transfer_to_unified(self, amount=1000):
        """Transfer from Funding to Unified Trading Account"""
        try:
            # Transfer from Funding to Unified
            transfer = self.client.create_internal_transfer(
                transferId=str(int(time.time())),  # Unique transfer ID
                coin="USDT",
                amount=str(amount),
                fromAccountType="FUND",
                toAccountType="UNIFIED"
            )
            
            if transfer and transfer.get('result'):
                logger.info(f"Successfully transferred {amount} USDT to Unified Account")
                return True
            else:
                logger.error(f"Transfer failed: {transfer}")
                return False
                
        except Exception as e:
            logger.error(f"Transfer error: {str(e)}")
            return False

    def check_funding_balance(self):
        """Check Funding wallet USDT balance"""
        try:
            # Get funding wallet balance
            wallet_info = self.client.get_wallet_balance(
                accountType="FUND",
                coin="USDT"
            )
            
            if wallet_info and wallet_info.get('result'):
                balance = wallet_info['result']['list'][0]['totalAvailableBalance']
                logger.info(f"Funding wallet balance: {balance} USDT")
                return float(balance)
            else:
                logger.error("Could not get funding wallet balance")
                return 0
                
        except Exception as e:
            logger.error(f"Error checking funding balance: {str(e)}")
            return 0

    def get_market_info(self, symbol):
        """Get market information for symbol"""
        try:
            response = self.client.get_tickers(
                category="linear",
                symbol=symbol
            )
            return response.get('result', {})
        except Exception as e:
            logger.error(f"Error getting market info: {str(e)}")
            return None 

    def get_position_info(self):
        """Get current position information"""
        try:
            response = self.client.get_positions(
                category="linear",
                symbol=self.symbol
            )
            
            if response and response.get('result', {}).get('list'):
                return response['result']['list'][0]
            return None
            
        except Exception as e:
            logger.error(f"Error getting position info: {str(e)}")
            return None
            
    def get_order_history(self):
        """Get recent orders"""
        try:
            response = self.client.get_orders(
                category="linear",
                symbol=self.symbol,
                limit=5  # Son 5 emir
            )
            
            if response and response.get('retCode') == 0:
                return response.get('result', {}).get('list', [])
            return []
            
        except Exception as e:
            logger.error(f"Error getting orders: {str(e)}")
            return []

    def get_positions(self):
        """Get all open positions"""
        try:
            response = self.client.get_position_info(
                category="linear",
                symbol=self.symbol
            )
            
            if response and response.get('retCode') == 0:
                positions = response.get('result', {}).get('list', [])
                return [pos for pos in positions if float(pos.get('size', 0)) > 0]
            return []
            
        except Exception as e:
            logger.error(f"Error getting positions: {str(e)}")
            return []

    def get_wallet_info(self):
        """Get wallet information"""
        try:
            response = self.client.get_wallet_balance(
                accountType="UNIFIED"
            )
            
            if response and response.get('retCode') == 0:
                wallets = response.get('result', {}).get('list', [])
                # USDT cüzdanını bul
                for wallet in wallets:
                    if wallet.get('coin') == 'USDT':
                        return wallet
            return None
            
        except Exception as e:
            logger.error(f"Error getting wallet info: {str(e)}")
            return None 