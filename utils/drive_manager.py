import os
import io
import json
import threading
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

class DriveManager:
    SCOPES = ['https://www.googleapis.com/auth/drive.file']

    def __init__(self, config):
        self.config = config
        self.credentials_path = 'data/credentials.json'
        self.tokens_dir = 'data/tokens'
        os.makedirs(self.tokens_dir, exist_ok=True)
        # FIXED: Use thread-local storage! Google API client is NOT thread-safe!
        self._local = threading.local()

    def authenticate(self, account_id):
        """Authenticate and return a thread-safe service instance"""
        # Ensure thread has its own dictionary
        if not hasattr(self._local, 'services'):
            self._local.services = {}
            
        # Return existing service for this thread if valid
        if account_id in self._local.services:
            return self._local.services[account_id]

        token_path = os.path.join(self.tokens_dir, f'token_{account_id}.json')
        creds = None
        
        if os.path.exists(token_path):
            try:
                creds = Credentials.from_authorized_user_file(token_path, self.SCOPES)
            except Exception as e:
                print(f"⚠️ Token corrupt for {account_id}: {e}")
            
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"⚠️ Token refresh failed: {e}")
                    creds = None
                    
            if not creds:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(f"Missing {self.credentials_path} - Cannot OAuth!")
                
                print(f"🛑 WAITING FOR BROWSER AUTH: {account_id}")
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, self.SCOPES)
                creds = flow.run_local_server(port=0, message=f"Please authenticate for Google Drive Account: {account_id}")
            
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        
        # Build new service for this specific thread
        service = build('drive', 'v3', credentials=creds)
        self._local.services[account_id] = service
        return service

    def get_folder_id(self, service, folder_name):
        """Find or create a folder on Drive"""
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        try:
            results = service.files().list(q=query, fields="files(id)").execute()
            files = results.get('files', [])
            
            if files:
                return files[0]['id']
            else:
                file_metadata = {
                    'name': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                folder = service.files().create(body=file_metadata, fields='id').execute()
                return folder.get('id')
        except Exception as e:
            print(f"❌ Drive folder error: {e}")
            raise

    def upload_file(self, account_id, local_path, drive_folder_name):
        """Upload a local file to a specific Drive account"""
        service = self.authenticate(account_id)
        folder_id = self.get_folder_id(service, drive_folder_name)
        
        filename = os.path.basename(local_path)
        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }
        
        # Use a safe mimetype to prevent crashes
        media = MediaFileUpload(local_path, mimetype='audio/mpeg', resumable=True)
        
        try:
            # Check if file already exists
            query = f"name = '{filename}' and '{folder_id}' in parents and trashed = false"
            results = service.files().list(q=query, fields="files(id)").execute()
            existing_files = results.get('files', [])
            
            if existing_files:
                file = service.files().update(fileId=existing_files[0]['id'], media_body=media).execute()
            else:
                file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                
            return file.get('id')
        except Exception as e:
            print(f"❌ Drive upload error: {e}")
            return None

    def upload_transition(self, local_path):
        """FIXED: Added missing method! Uploads mix to account_1 and gets sharable link for Mobile Testing."""
        if not os.path.exists(local_path):
            print("❌ Mix file not found for upload!")
            return None
            
        try:
            # Always use account_1 for transitions
            account_id = self.config.get('storage', {}).get('drive_accounts', ['account_1'])[0]
            service = self.authenticate(account_id)
            folder_id = self.get_folder_id(service, 'DJ_Transitions')
            
            filename = os.path.basename(local_path)
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            
            media = MediaFileUpload(local_path, mimetype='audio/wav', resumable=True)
            file = service.files().create(
                body=file_metadata, 
                media_body=media, 
                fields='id, webViewLink'
            ).execute()
            
            file_id = file.get('id')
            
            # Make public so phone can play it without logging in
            permission = {
                'type': 'anyone',
                'role': 'reader',
            }
            service.permissions().create(fileId=file_id, body=permission).execute()
            
            return file.get('webViewLink')
            
        except Exception as e:
            print(f"❌ Failed to upload transition to Drive: {e}")
            return None

    def download_file(self, account_id, drive_file_id, local_path):
        """Download a file from Drive"""
        try:
            service = self.authenticate(account_id)
            request = service.files().get_media(fileId=drive_file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            with open(local_path, 'wb') as f:
                f.write(fh.getvalue())
            return local_path
        except Exception as e:
            print(f"❌ Drive download error: {e}")
            return None
