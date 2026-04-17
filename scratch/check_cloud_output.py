import os
import sys
sys.path.append(os.getcwd())
import yaml
from utils.drive_manager import DriveManager

def main():
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    dm = DriveManager(config)
    acc_id = 'account_1'
    service = dm.authenticate(acc_id)
    
    parent_id = dm.get_folder_id(service, 'COLAB_OUTPUT')
    q = f"'{parent_id}' in parents and trashed = false"
    res = service.files().list(q=q, fields='files(name, id)').execute()
    files = res.get('files', [])
    
    print(f"COLAB_OUTPUT_FILES: {files}")

if __name__ == "__main__":
    main()
