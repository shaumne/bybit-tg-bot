import requests
from datetime import datetime
import json
from utils.logger import setup_logger
from config.settings import settings

logger = setup_logger('announcements')

class LaunchpoolAnnouncements:
    def __init__(self):
        self.last_check_time = datetime.now()
        self.check_interval = settings.CHECK_INTERVAL
    
    def check_new_listings(self):
        """Check new Launchpool listings"""
        try:
            logger.info("Checking Launchpool announcements...")
            
            params = {
                'locale': 'en-US',
                'category': 'spot',
                'limit': 20,
                'tag': 'Launchpool'
            }
            
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                'https://api.bybit.com/v5/announcements/index',
                params=params,
                headers=headers
            )
            
            if response.status_code != 200:
                logger.error(f"API Error: {response.status_code}")
                return None
                
            data = response.json()
            
            if data.get('retCode') != 0:
                logger.error(f"API Response Error: {data}")
                return None
                
            announcements = data.get('result', {}).get('list', [])
            
            if announcements:
                latest = announcements[0]
                announcement_time = datetime.fromtimestamp(
                    int(latest.get('dateTimestamp', 0)) / 1000
                )
                
                if announcement_time > self.last_check_time:
                    logger.info(f"New Launchpool Found: {latest['title']}")
                    self.last_check_time = datetime.now()
                    return latest
                    
            return None
            
        except Exception as e:
            logger.error(f"Announcement check error: {str(e)}")
            return None 