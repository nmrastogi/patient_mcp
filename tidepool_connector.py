import asyncio
import aiohttp
import base64
import json
import os
import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from urllib.parse import urlencode, parse_qs

logger = logging.getLogger(__name__)

class TidepoolOAuth2Connector:
    """
    Modern Tidepool API connector using OAuth2/OIDC authentication
    """
    def __init__(self, use_integration_env: bool = True):
        # Use integration environment for development
        if use_integration_env:
            self.auth_base_url = "https://int-auth.tidepool.org"
            self.api_base_url = "https://int-api.tidepool.org"
        else:
            self.auth_base_url = "https://auth.tidepool.org"
            self.api_base_url = "https://api.tidepool.org"
        
        # OAuth2 configuration
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = "http://localhost:8080/callback"  # For development
        
        # Token storage
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        self.user_id = None
        
        # Session
        self.session = None
    
    async def register_oauth_client(self, client_name: str = "Diabetes MCP Server") -> Dict:
        """
        Register a new OAuth2 client with Tidepool
        Note: This may require manual approval from Tidepool team
        """
        registration_url = f"{self.auth_base_url}/oauth2/register"
        
        client_metadata = {
            "client_name": client_name,
            "redirect_uris": [self.redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "scope": "openid profile email offline_access",
            "token_endpoint_auth_method": "client_secret_basic"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(registration_url, json=client_metadata) as response:
                    if response.status == 201:
                        client_data = await response.json()
                        self.client_id = client_data.get("client_id")
                        self.client_secret = client_data.get("client_secret")
                        
                        logger.info(f"OAuth2 client registered successfully")
                        logger.info(f"Client ID: {self.client_id}")
                        logger.warning("Save your client_secret securely - it won't be shown again!")
                        
                        return client_data
                    else:
                        error_text = await response.text()
                        logger.error(f"Client registration failed: {response.status} - {error_text}")
                        return {}
        except Exception as e:
            logger.error(f"Error registering OAuth2 client: {e}")
            return {}
    
    def get_authorization_url(self, state: str = None) -> str:
        """
        Get the authorization URL for OAuth2 flow
        User needs to visit this URL to authorize the application
        """
        if not self.client_id:
            raise Exception("Client not registered. Call register_oauth_client() first.")
        
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "openid profile email offline_access",
            "state": state or "diabetes_mcp_auth"
        }
        
        auth_url = f"{self.auth_base_url}/oauth2/authorize?" + urlencode(params)
        return auth_url
    
    async def exchange_code_for_tokens(self, authorization_code: str) -> bool:
        """
        Exchange authorization code for access and refresh tokens
        """
        if not self.client_id or not self.client_secret:
            raise Exception("Client credentials not available")
        
        token_url = f"{self.auth_base_url}/oauth2/token"
        
        # Prepare client credentials
        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        
        headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": self.redirect_uri
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(token_url, headers=headers, data=data) as response:
                    if response.status == 200:
                        token_data = await response.json()
                        
                        self.access_token = token_data.get("access_token")
                        self.refresh_token = token_data.get("refresh_token")
                        
                        # Calculate expiration time
                        expires_in = token_data.get("expires_in", 3600)
                        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                        
                        # Get user info
                        await self._get_user_info()
                        
                        logger.info("Successfully obtained access tokens")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Token exchange failed: {response.status} - {error_text}")
                        return False
        except Exception as e:
            logger.error(f"Error exchanging code for tokens: {e}")
            return False
    
    async def refresh_access_token(self) -> bool:
        """
        Refresh the access token using refresh token
        """
        if not self.refresh_token:
            logger.error("No refresh token available")
            return False
        
        token_url = f"{self.auth_base_url}/oauth2/token"
        
        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        
        headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(token_url, headers=headers, data=data) as response:
                    if response.status == 200:
                        token_data = await response.json()
                        
                        self.access_token = token_data.get("access_token")
                        if token_data.get("refresh_token"):
                            self.refresh_token = token_data.get("refresh_token")
                        
                        expires_in = token_data.get("expires_in", 3600)
                        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                        
                        logger.info("Access token refreshed successfully")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Token refresh failed: {response.status} - {error_text}")
                        return False
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return False
    
    async def _get_user_info(self):
        """Get user information from the userinfo endpoint"""
        if not self.access_token:
            return
        
        userinfo_url = f"{self.auth_base_url}/oauth2/userinfo"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(userinfo_url, headers=headers) as response:
                    if response.status == 200:
                        user_data = await response.json()
                        self.user_id = user_data.get("sub")  # Subject ID
                        logger.info(f"User authenticated: {user_data.get('email', 'Unknown')}")
                    else:
                        logger.warning(f"Failed to get user info: {response.status}")
        except Exception as e:
            logger.warning(f"Error getting user info: {e}")
    
    async def ensure_valid_token(self):
        """Ensure we have a valid access token, refresh if needed"""
        if not self.access_token:
            raise Exception("No access token. Complete OAuth2 flow first.")
        
        # Check if token is expired (with 5 minute buffer)
        if self.token_expires_at and datetime.now() >= (self.token_expires_at - timedelta(minutes=5)):
            success = await self.refresh_access_token()
            if not success:
                raise Exception("Failed to refresh access token")
    
    async def fetch_diabetes_data(self, days_back: int = 30, data_types: List[str] = None) -> List[Dict]:
        """
        Fetch diabetes data from Tidepool API
        """
        await self.ensure_valid_token()
        
        if not self.user_id:
            raise Exception("User ID not available")
        
        if data_types is None:
            data_types = ['cbg', 'smbg', 'bolus', 'basal', 'wizard', 'food']
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Tidepool expects ISO 8601 format with Z suffix
        start_iso = start_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        end_iso = end_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        
        data_url = f"{self.api_base_url}/data/{self.user_id}"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        params = {
            'startDate': start_iso,
            'endDate': end_iso,
            'type': ','.join(data_types)
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(data_url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Fetched {len(data)} records from Tidepool")
                        return data
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to fetch data: {response.status} - {error_text}")
                        return []
        except Exception as e:
            logger.error(f"Error fetching Tidepool data: {e}")
            return []
    
    def save_credentials(self, filepath: str = ".tidepool_credentials.json"):
        """Save OAuth2 credentials to file"""
        credentials = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_expires_at": self.token_expires_at.isoformat() if self.token_expires_at else None,
            "user_id": self.user_id
        }
        
        with open(filepath, 'w') as f:
            json.dump(credentials, f, indent=2)
        
        logger.info(f"Credentials saved to {filepath}")
    
    def load_credentials(self, filepath: str = ".tidepool_credentials.json") -> bool:
        """Load OAuth2 credentials from file"""
        try:
            with open(filepath, 'r') as f:
                credentials = json.load(f)
            
            self.client_id = credentials.get("client_id")
            self.client_secret = credentials.get("client_secret")
            self.access_token = credentials.get("access_token")
            self.refresh_token = credentials.get("refresh_token")
            self.user_id = credentials.get("user_id")
            
            expires_str = credentials.get("token_expires_at")
            if expires_str:
                self.token_expires_at = datetime.fromisoformat(expires_str)
            
            logger.info("Credentials loaded successfully")
            return True
        except FileNotFoundError:
            logger.info("No saved credentials found")
            return False
        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
            return False

class TidepoolDataProcessor:
    """
    Enhanced data processor for Tidepool OAuth2 data
    """
    
    @staticmethod
    def process_tidepool_data(raw_data: List[Dict]) -> pd.DataFrame:
        """
        Convert Tidepool data to standardized DataFrame format
        """
        records = []
        
        for entry in raw_data:
            try:
                # Base record with common fields
                record = {
                    'timestamp': pd.to_datetime(entry.get('time')),
                    'type': entry.get('type'),
                    'device_id': entry.get('deviceId', ''),
                    'upload_id': entry.get('uploadId', ''),
                    'source': 'tidepool_oauth2'
                }
                
                # Process different data types
                data_type = entry.get('type')
                
                if data_type == 'cbg':  # Continuous Glucose Monitor
                    record.update({
                        'glucose_mg_dl': entry.get('value'),
                        'glucose_mmol_l': entry.get('value') * 0.0555 if entry.get('value') else None,
                        'trend_direction': entry.get('trend'),
                        'trend_rate': entry.get('trendRate'),
                        'data_source': 'cgm',
                        'units': entry.get('units', 'mg/dL')
                    })
                
                elif data_type == 'smbg':  # Self-Monitored Blood Glucose
                    record.update({
                        'glucose_mg_dl': entry.get('value'),
                        'glucose_mmol_l': entry.get('value') * 0.0555 if entry.get('value') else None,
                        'data_source': 'fingerstick',
                        'units': entry.get('units', 'mg/dL'),
                        'sub_type': entry.get('subType')
                    })
                
                elif data_type == 'bolus':  # Insulin Bolus
                    normal_bolus = entry.get('normal', 0)
                    extended_bolus = entry.get('extended', 0)
                    
                    record.update({
                        'insulin_bolus_normal': normal_bolus,
                        'insulin_bolus_extended': extended_bolus,
                        'insulin_bolus_total': normal_bolus + extended_bolus,
                        'bolus_duration': entry.get('duration'),
                        'bolus_sub_type': entry.get('subType', 'normal'),
                        'insulin_type': 'bolus'
                    })
                
                elif data_type == 'basal':  # Basal Insulin
                    record.update({
                        'insulin_basal_rate': entry.get('rate'),
                        'basal_duration_ms': entry.get('duration'),
                        'basal_duration_hours': entry.get('duration') / (1000 * 60 * 60) if entry.get('duration') else None,
                        'basal_delivery_type': entry.get('deliveryType', 'scheduled'),
                        'insulin_type': 'basal'
                    })
                
                elif data_type == 'wizard':  # Bolus Calculator
                    record.update({
                        'carb_input': entry.get('carbInput'),
                        'bg_input': entry.get('bgInput'),
                        'insulin_sensitivity_factor': entry.get('insulinSensitivity'),
                        'carb_ratio': entry.get('insulinCarbRatio'),
                        'bg_target_low': entry.get('bgTarget', {}).get('low'),
                        'bg_target_high': entry.get('bgTarget', {}).get('high'),
                        'recommended_net': entry.get('recommended', {}).get('net'),
                        'recommended_carb': entry.get('recommended', {}).get('carb'),
                        'recommended_correction': entry.get('recommended', {}).get('correction'),
                        'bolus_id': entry.get('bolus')
                    })
                
                elif data_type == 'food':  # Meal/Food Data
                    nutrition = entry.get('nutrition', {})
                    carbs = 0
                    
                    if 'carbohydrate' in nutrition:
                        carb_data = nutrition['carbohydrate']
                        if isinstance(carb_data, dict):
                            carbs = carb_data.get('net', 0)
                        else:
                            carbs = carb_data
                    
                    record.update({
                        'food_carbs': carbs,
                        'food_protein': nutrition.get('protein', 0),
                        'food_fat': nutrition.get('fat', 0),
                        'food_calories': nutrition.get('calories', 0),
                        'meal_title': entry.get('prescriptor', 'unknown'),
                        'meal_ingredients': entry.get('ingredients', [])
                    })
                
                records.append(record)
                
            except Exception as e:
                logger.warning(f"Error processing Tidepool entry: {e}")
                continue
        
        if not records:
            return pd.DataFrame()
        
        df = pd.DataFrame(records)
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Add derived fields
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.day_name()
        df['date'] = df['timestamp'].dt.date
        
        logger.info(f"Processed {len(df)} Tidepool records into DataFrame")
        return df

# OAuth2 Setup Helper
async def setup_tidepool_oauth():
    """
    Interactive setup for Tidepool OAuth2 integration
    """
    print("=== Tidepool OAuth2 Setup ===")
    
    connector = TidepoolOAuth2Connector(use_integration_env=True)
    
    # Try to load existing credentials
    if connector.load_credentials():
        print("✅ Existing credentials loaded")
        
        # Test if tokens are still valid
        try:
            await connector.ensure_valid_token()
            print("✅ Tokens are valid")
            return connector
        except:
            print("⚠️ Tokens expired, need to re-authenticate")
    
    # Check if we have client credentials
    if not connector.client_id:
        print("\n1. Registering OAuth2 client...")
        client_data = await connector.register_oauth_client()
        
        if not client_data:
            print("❌ Failed to register client. You may need to contact Tidepool for manual approval.")
            return None
    
    # Get authorization
    print("\n2. Getting authorization...")
    auth_url = connector.get_authorization_url()
    
    print(f"Visit this URL to authorize the application:")
    print(f"{auth_url}")
    print()
    
    # In a real application, you'd implement a proper callback handler
    auth_code = input("Enter the authorization code from the callback URL: ")
    
    success = await connector.exchange_code_for_tokens(auth_code)
    if success:
        print("✅ Authorization successful!")
        connector.save_credentials()
        return connector
    else:
        print("❌ Authorization failed")
        return None

# Test function
async def test_tidepool_oauth():
    """Test Tidepool OAuth2 connection and data fetching"""
    connector = await setup_tidepool_oauth()
    
    if not connector:
        print("❌ Failed to set up Tidepool connection")
        return
    
    try:
        # Test data fetch
        print("\n3. Fetching diabetes data...")
        data = await connector.fetch_diabetes_data(days_back=7)
        print(f"✅ Fetched {len(data)} records")
        
        # Test data processing
        if data:
            processor = TidepoolDataProcessor()
            df = processor.process_tidepool_data(data)
            print(f"✅ Processed into DataFrame with {len(df)} rows")
            
            # Show data types
            if not df.empty:
                data_types = df['type'].value_counts()
                print("Data types found:")
                for dtype, count in data_types.items():
                    print(f"  {dtype}: {count}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_tidepool_oauth())