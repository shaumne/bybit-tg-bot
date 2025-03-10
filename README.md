# Bybit Launchpool Trading Bot 🤖

An automated trading bot for Bybit Launchpool announcements with Telegram integration.

---

## FEATURES
- 🚀 **Telegram bot control interface**
- 🔔 **Automatic Launchpool announcement monitoring**
- ⚙️ **Customizable trading parameters**
- 🔒 **Secure password protection**
- 📡 **Real-time notifications**
- 🧪 **Test mode support**

---

## INSTALLATION & SETUP
### 1. System Requirements
- Python 3.8 or higher
- pip (Python package manager)
- Git (optional)

### 2. Download the Repository
- Download the latest version of the bot as a ZIP file from [here](https://github.com/shaumne/bybit-tg-bot/archive/refs/heads/main.zip)
- Unzip the downloaded file

### 3. Create Virtual Environment
- Open a terminal and navigate to the bot folder
- Create a virtual environment:
  ````python -m venv venv````
  
- Activate the virtual environment:
  - **For Windows:**
    ````venv\Scripts\activate````
  - **For Linux/Mac:**
    ````source venv/bin/activate````

### 4. Install Dependencies
- Install required dependencies:
  ````pip install -r requirements.txt````

### 5. Configuration Setup
1. Copy `.env.example` to `.env`
2. Open `.env` file and configure the following settings:
   - **Bot Settings**  
     ```
     TELEGRAM_BOT_TOKEN=your_telegram_bot_token
     TELEGRAM_CHAT_ID=your_chat_id
     ```
   - **Bybit API Settings**  
     ```
     BYBIT_API_KEY=your_api_key
     BYBIT_API_SECRET=your_api_secret
     TESTNET=true
     ```
   - **Trading Settings**  
     ```
     TRADE_SYMBOL=MNTUSDT
     TRADE_QUANTITY=100
     STOP_LOSS_PERCENTAGE=2.0
     TAKE_PROFIT_PERCENTAGE=4.0
     MAX_POSITION_SIZE=1000
     ```
   - **Other Settings**  
     ```
     CHECK_INTERVAL=60
     RETRY_DELAY=5
     MAX_RETRIES=3
     ```

### 6. Getting Telegram Credentials
1. **Create a new bot**:  
   - Message @BotFather on Telegram  
   - Use the `/newbot` command  
   - Follow the instructions to create the bot  
   - Copy the provided API token

2. **Get your Chat ID**:  
   - Message @userinfobot on Telegram  
   - Copy your ID number

### 7. Getting Bybit API Credentials
1. **Create Bybit Account**:  
   - Sign up at [Bybit](https://www.bybit.com)  
   - Complete verification if required

2. **Generate API Keys**:  
   - Go to Account Settings > API Management  
   - Create a new API key with trading permissions  
   - Save your API Key and Secret securely

### 8. Starting the Bot
1. Run the bot:
   ````python main.py````

2. First-time setup in Telegram:
   - Start a chat with your bot
   - Set an initial password when prompted
   - Configure trading parameters

---

## USAGE GUIDE

### Basic Commands
- `/start` - Begin interaction with the bot
- `/help` - Show available commands
- `/settings` - Configure trading parameters

### Trading Parameters
- **Quantity**: Trade size in USDT
- **Stop Loss**: Percentage for stop loss
- **Take Profit**: Percentage for take profit
- **Leverage**: Trading leverage (1-100x)

### Security Features
- **Password protection**
- **Chat ID verification**
- **API key encryption**

---

## IMPORTANT NOTES

1. **Testing**:  
   - Always start with ````TESTNET=true````  
   - Use small amounts for initial trades  
   - Monitor bot behavior before live trading

2. **Security**:  
   - Never share your API keys  
   - Use strong passwords  
   - Keep the `.env` file secure

3. **Risk Management**:  
   - Start with small positions  
   - Use appropriate stop losses  
   - Monitor the bot regularly

---

## TROUBLESHOOTING

### Common Issues and Solutions:

1. **Connection Errors**:  
   - Check your internet connection  
   - Verify API credentials  
   - Ensure Bybit services are available

2. **Authentication Issues**:  
   - Verify your Telegram token  
   - Double-check your Chat ID  
   - Confirm API permissions

3. **Trading Errors**:  
   - Check your account balance  
   - Verify trading parameters  
   - Ensure the market is active

---

## ADDITIONAL RESOURCES
- [Bybit API Documentation](https://bybit-exchange.github.io/docs/v5/intro)
- [Python-Telegram-Bot Documentation](https://python-telegram-bot.readthedocs.io)
- [Pybit Documentation](https://pybit.readthedocs.io)

---

## CONTRIBUTING

Contributions are welcome! Please feel free to submit a Pull Request.

---

## LICENSE
This project is licensed under the MIT License - see the LICENSE file for details.

---

## SUPPORT
For support, please open an issue in the GitHub repository or contact the maintainers.

---

## DISCLAIMER
Trading cryptocurrencies involves risk. This bot is for educational purposes only.  
Always do your own research and trade responsibly.

