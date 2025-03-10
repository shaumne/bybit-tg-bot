from pybit.unified_trading import HTTP
import os
from utils.logger import setup_logger
from dotenv import load_dotenv
from config.settings import (
    API_KEY, API_SECRET, TESTNET, SYMBOL, 
    QUANTITY, MAX_POSITION, STOP_LOSS_PCT, 
    TAKE_PROFIT_PCT
)
import time
import math

# Load .env
load_dotenv()

logger = setup_logger('trade')

class TradeExecutor:
    def __init__(self):
        """Initialize TradeExecutor"""
        try:
            self.api_key = os.getenv('BYBIT_API_KEY')
            self.api_secret = os.getenv('BYBIT_API_SECRET')
            self.testnet = os.getenv('TESTNET', 'true').lower() == 'true'
            self.symbol = os.getenv('TRADE_SYMBOL', 'MNTUSDT')
            
            if not self.api_key or not self.api_secret:
                logger.error("Bybit credentials not found in .env!")
                raise ValueError("Bybit credentials not found!")
            
            # Initialize Bybit session
            self.session = HTTP(
                testnet=self.testnet,
                api_key=self.api_key,
                api_secret=self.api_secret
            )
            
            logger.info(f"TradeExecutor initialized. Testnet: {self.testnet}")
            
        except Exception as e:
            logger.error(f"TradeExecutor initialization error: {str(e)}")
            raise
            
    def get_min_trading_qty(self):
        """Get minimum trading quantity for symbol"""
        try:
            instruments = self.session.get_instruments_info(
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
            wallet_info = self.session.get_wallet_balance(
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
            instruments = self.session.get_instruments_info(
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

    def execute_trade(self, side="Buy", quantity=None, sl_percentage=None, tp_percentage=None, leverage=None):
        """Execute trade on Bybit"""
        try:
            # Get current price first
            ticker = self.session.get_tickers(
                category="linear",
                symbol=self.symbol
            )
            
            if not ticker or not ticker.get('result'):
                raise Exception("Could not get current price")
                
            current_price = float(ticker['result']['list'][0]['lastPrice'])
            
            # Calculate stop loss and take profit prices
            if side == "Buy":
                stop_loss = round(current_price * (1 - sl_percentage/100), 4)
                take_profit = round(current_price * (1 + tp_percentage/100), 4)
            else:
                stop_loss = round(current_price * (1 + sl_percentage/100), 4)
                take_profit = round(current_price * (1 - tp_percentage/100), 4)

            # Place the order
            try:
                order = self.session.place_order(
                    category="linear",
                    symbol=self.symbol,
                    side=side,
                    orderType="Market",
                    qty=str(quantity),
                    stopLoss=str(stop_loss),
                    takeProfit=str(take_profit),
                    timeInForce="GTC",
                    positionIdx=0
                )
                
                if order and order.get('result'):
                    logger.info(f"Trade executed: {order['result']}")
                    return {
                        'symbol': self.symbol,
                        'price': current_price,
                        'quantity': quantity,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'leverage': leverage
                    }
                else:
                    raise Exception(f"Order failed: {order}")
                    
            except Exception as e:
                logger.error(f"Order placement error: {str(e)}")
                raise
                
        except Exception as e:
            logger.error(f"Trade execution error: {str(e)}")
            raise

    def transfer_to_unified(self, amount=1000):
        """Transfer from Funding to Unified Trading Account"""
        try:
            # Transfer from Funding to Unified
            transfer = self.session.create_internal_transfer(
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
            wallet_info = self.session.get_wallet_balance(
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