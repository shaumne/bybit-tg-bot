from pybit.unified_trading import HTTP
import os
from utils.logger import setup_logger
from dotenv import load_dotenv
from config.settings import settings
import time
import math

# Load .env
load_dotenv()

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
            
            logger.info(f"TradeExecutor initialized. Testnet: {settings.TESTNET}")
            
        except Exception as e:
            logger.error(f"TradeExecutor initialization error: {str(e)}")
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

    def execute_trade(self, side, quantity, sl_percentage, tp_percentage, leverage, category="linear"):
        """Execute trade with given parameters"""
        try:
            # Trade parameters
            params = {
                'category': category,
                'symbol': self.symbol,
                'side': side,
                'orderType': 'Market',
                'qty': str(quantity)
            }

            # Execute trade first
            result = self.client.place_order(**params)
            
            if result and result.get('retCode') == 0:
                order_result = result.get('result', {})
                
                # After successful order, set leverage and stop loss/take profit
                try:
                    self.client.set_leverage(
                        symbol=self.symbol,
                        buyLeverage=str(leverage),
                        sellLeverage=str(leverage),
                        category=category
                    )
                    
                    # Set stop loss and take profit
                    self.client.set_trading_stop(
                        category=category,
                        symbol=self.symbol,
                        stopLoss=str(sl_percentage),
                        takeProfit=str(tp_percentage),
                        positionIdx=0
                    )
                except Exception as e:
                    logger.warning(f"Could not set leverage/SL/TP: {str(e)}")
                
                # Get order details
                try:
                    order_details = self.client.get_order_history(
                        category=category,
                        symbol=self.symbol,
                        orderId=order_result.get('orderId')
                    )
                    
                    if order_details and order_details.get('result', {}).get('list'):
                        executed_order = order_details['result']['list'][0]
                        return {
                            'price': executed_order.get('avgPrice', '0'),
                            'quantity': executed_order.get('qty', quantity),
                            'stop_loss': sl_percentage,
                            'take_profit': tp_percentage
                        }
                    
                except Exception as e:
                    logger.warning(f"Could not get order details: {str(e)}")
                
                # Fallback return if can't get order details
                return {
                    'price': order_result.get('avgPrice', '0'),
                    'quantity': order_result.get('qty', quantity),
                    'stop_loss': sl_percentage,
                    'take_profit': tp_percentage
                }
            else:
                logger.error(f"Trade failed: {result}")
                raise Exception(f"Trade failed: {result.get('retMsg', 'Unknown error')}")

        except Exception as e:
            logger.error(f"Trade execution error: {str(e)}")
            raise

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