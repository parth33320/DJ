import os
import sys
import yaml
from main import DJApp

def setup():
    print("==================================================")
    print("📁 GOOGLE DRIVE STORAGE SETUP")
    print("==================================================")
    print("This will open your browser to authorize access to")
    print("your Google Drive accounts for song storage.")
    print("==================================================\n")

    app = DJApp()
    
    # Check for credentials.json
    if not os.path.exists('data/credentials.json'):
        print("❌ Error: data/credentials.json not found!")
        print("I've tried searching for it, but if it's missing, you'll need to")
        print("download a new OAuth Client ID from Google Cloud Console.")
        return

    try:
        accounts = app.config['storage'].get('drive_accounts', ['account_1'])
        print(f"Detected {len(accounts)} accounts in config.\n")

        for idx, acc_id in enumerate(accounts):
            print(f"Step {idx+1}: Authenticating {acc_id}...")
            app.drive_manager.authenticate(acc_id)
            print(f"✅ {acc_id} ready!\n")
        
        print(f"🎉 All {len(accounts)} Google Drives are now connected!")
        print("The DJ app will now automatically offload songs to these drives")
        print("to save space on your local C:\\ drive.")
        
    except Exception as e:
        print(f"❌ Setup failed: {e}")

if __name__ == "__main__":
    setup()
