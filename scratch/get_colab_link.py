import os
import sys
sys.path.append(os.getcwd())
import yaml
from utils.drive_manager import DriveManager

def main():
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        
    dm = DriveManager(config)
    
    for i in range(1, 6):
        acc_id = f'account_{i}'
        try:
            print(f"--- Processing {acc_id} ---")
            service = dm.authenticate(acc_id)
            file_id = dm.upload_file(acc_id, 'docs/Colab_Splicer.ipynb', 'root')
            res = service.files().get(fileId=file_id, fields='webViewLink').execute()
            print(f"{acc_id}_LINK: {res.get('webViewLink')}")
        except Exception as e:
            print(f"--- Failed {acc_id}: {e} ---")

if __name__ == "__main__":
    main()
