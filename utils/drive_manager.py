"""
Google Drive Manager - 5 Account Round Robin with Smart Indexing
Stores MP3s, stems, transitions on Drive to save local space.
Tracks which account has what data!
"""

import os
import io
import json
import threading
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
        self.index_path = 'data/drive_index.json'
        os.makedirs(self.tokens_dir, exist_ok=True)
        
        # Thread-safe service cache
        self._local = threading.local()
        
        # Load account index (tracks which account has what)
        self.index = self._load_index()
        
        # Get accounts from config
        self.accounts = config.get('storage', {}).get('drive_accounts', ['account_1'])
        
        # Storage limit per account (15GB free, use 14GB to be safe)
        self.max_bytes_per_account = 14 * 1024 * 1024 * 1024  # 14GB

    def _load_index(self):
        """Load index tracking which account has what files"""
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            'files': {},           # file_id -> {account, path, size}
            'account_usage': {},   # account_id -> bytes_used
            'current_account_idx': 0
        }
    
    def _save_index(self):
        """Save index to disk"""
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        with open(self.index_path, 'w') as f:
            json.dump(self.index, f, indent=2)
    
    def _get_best_account(self, file_size_bytes: int) -> str:
        """Get the best account to store a file (round robin with space check)"""
        # Start from current index
        start_idx = self.index.get('current_account_idx', 0)
        
        for i in range(len(self.accounts)):
            idx = (start_idx + i) % len(self.accounts)
            account_id = self.accounts[idx]
            
            # Check usage
            usage = self.index.get('account_usage', {}).get(account_id, 0)
            
            if usage + file_size_bytes < self.max_bytes_per_account:
                # This account has space!
                self.index['current_account_idx'] = (idx + 1) % len(self.accounts)
                self._save_index()
                return account_id
        
        # All accounts full! Use the one with most space
        min_usage = float('inf')
        best_account = self.accounts[0]
        for account_id in self.accounts:
            usage = self.index.get('account_usage', {}).get(account_id, 0)
            if usage < min_usage:
                min_usage = usage
                best_account = account_id
        
        print(f"⚠️ All accounts nearly full! Using {best_account}")
        return best_account

    def authenticate(self, account_id):
        """Authenticate and return a thread-safe service instance"""
        if not hasattr(self._local, 'services'):
            self._local.services = {}
            
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
                    raise FileNotFoundError(f"Missing {self.credentials_path}")
                
                print(f"🛑 WAITING FOR BROWSER AUTH: {account_id}")
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        
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
        file_size = os.path.getsize(local_path)
        
        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }
        
        media = MediaFileUpload(local_path, resumable=True)
        
        try:
            # Check if file already exists
            query = f"name = '{filename}' and '{folder_id}' in parents and trashed = false"
            results = service.files().list(q=query, fields="files(id)").execute()
            existing_files = results.get('files', [])
            
            if existing_files:
                file = service.files().update(fileId=existing_files[0]['id'], media_body=media).execute()
                file_id = existing_files[0]['id']
            else:
                file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                file_id = file.get('id')
            
            # Update index
            self.index['files'][file_id] = {
                'account': account_id,
                'folder': drive_folder_name,
                'filename': filename,
                'size': file_size
            }
            
            # Update account usage
            if account_id not in self.index['account_usage']:
                self.index['account_usage'][account_id] = 0
            self.index['account_usage'][account_id] += file_size
            
            self._save_index()
            return file_id
            
        except Exception as e:
            print(f"❌ Drive upload error: {e}")
            return None

    def upload_auto(self, local_path, drive_folder_name):
        """
        AUTO-UPLOAD: Picks the best account automatically!
        Uses round-robin with space checking.
        """
        file_size = os.path.getsize(local_path)
        account_id = self._get_best_account(file_size)
        
        print(f"☁️ Auto-uploading to {account_id}...")
        return self.upload_file(account_id, local_path, drive_folder_name)

    def upload_transition(self, local_path):
        """Upload a transition mix for mobile testing and AI learning"""
        if not os.path.exists(local_path):
            print("❌ Mix file not found for upload!")
            return None
            
        try:
            file_size = os.path.getsize(local_path)
            account_id = self._get_best_account(file_size)
            
            service = self.authenticate(account_id)
            folder_id = self.get_folder_id(service, 'DJ_Agent_Transitions')
            
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
            
            # Make public for mobile access
            permission = {'type': 'anyone', 'role': 'reader'}
            service.permissions().create(fileId=file_id, body=permission).execute()
            
            # Update index
            self.index['files'][file_id] = {
                'account': account_id,
                'folder': 'DJ_Agent_Transitions',
                'filename': filename,
                'size': file_size
            }
            if account_id not in self.index['account_usage']:
                self.index['account_usage'][account_id] = 0
            self.index['account_usage'][account_id] += file_size
            self._save_index()
            
            return file.get('webViewLink')
            
        except Exception as e:
            print(f"❌ Failed to upload transition: {e}")
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

    def find_file(self, filename):
        """Find which account has a specific file"""
        for file_id, info in self.index.get('files', {}).items():
            if info.get('filename') == filename:
                return {
                    'file_id': file_id,
                    'account': info['account'],
                    'folder': info['folder']
                }
        return None

    def get_storage_report(self):
        """Get storage usage report for all accounts"""
        report = []
        for account_id in self.accounts:
            usage = self.index.get('account_usage', {}).get(account_id, 0)
            usage_gb = usage / (1024 * 1024 * 1024)
            percent = (usage / self.max_bytes_per_account) * 100
            report.append({
                'account': account_id,
                'used_gb': round(usage_gb, 2),
                'percent': round(percent, 1)
            })
        return report
