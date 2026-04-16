import os
import io
import json
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
        self.services = {}

    def authenticate(self, account_id):
        """Authenticate for a specific account ID (e.g., 'account_1')"""
        token_path = os.path.join(self.tokens_dir, f'token_{account_id}.json')
        creds = None
        
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, self.SCOPES)
            
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(f"Missing {self.credentials_path}")
                
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, self.SCOPES)
                # Note: This will open a browser window for the user
                creds = flow.run_local_server(port=0, message=f"Please authenticate for Google Drive Account: {account_id}")
            
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        
        self.services[account_id] = build('drive', 'v3', credentials=creds)
        return self.services[account_id]

    def get_folder_id(self, service, folder_name):
        """Find or create a folder on Drive"""
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
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

    def upload_file(self, account_id, local_path, drive_folder_name):
        """Upload a local file to a specific Drive account"""
        if account_id not in self.services:
            self.authenticate(account_id)
        
        service = self.services[account_id]
        folder_id = self.get_folder_id(service, drive_folder_name)
        
        filename = os.path.basename(local_path)
        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }
        media = MediaFileUpload(local_path, resumable=True)
        
        # Check if file already exists to avoid duplicates
        query = f"name = '{filename}' and '{folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, fields="files(id)").execute()
        existing_files = results.get('files', [])
        
        if existing_files:
            file = service.files().update(fileId=existing_files[0]['id'], media_body=media).execute()
        else:
            file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            
        return file.get('id')

    def download_file(self, account_id, drive_file_id, local_path):
        """Download a file from Drive if we need it back locally for playback/analysis"""
        if account_id not in self.services:
            self.authenticate(account_id)
        
        service = self.services[account_id]
        request = service.files().get_media(fileId=drive_file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        with open(local_path, 'wb') as f:
            f.write(fh.getvalue())
        return local_path
