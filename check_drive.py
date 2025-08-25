import os
import json
import base64
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

def check_drive_permission():
    """Verifica todas as permissões do Drive"""
    
    creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
    creds_json = creds_json.strip()
    
    if creds_json.startswith('eyJ'):
        creds_json = base64.b64decode(creds_json).decode('utf-8')
    
    creds_dict = json.loads(creds_json)
    credentials = Credentials.from_service_account_info(creds_dict)
    
    drive_service = build('drive', 'v3', credentials=credentials)
    
    # 1. Verificar Shared Drive
    try:
        drive = drive_service.drives().get(driveId='1T3bLqnSCLg3_zkqnj5JXzH8tvN-h63yy').execute()
        print(f"✅ Shared Drive encontrado: {drive['name']}")
    except Exception as e:
        print(f"❌ Erro no Shared Drive: {e}")
    
    # 2. Verificar permissões de escrita
    try:
        file_metadata = {'name': 'test_permission.txt', 'mimeType': 'text/plain'}
        media = MediaIoBaseUpload(io.BytesIO(b'test content'), mimetype='text/plain')
        
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            supportsAllDrives=True
        ).execute()
        
        print(f"✅ Permissão de escrita OK - File ID: {file['id']}")
        
        # Limpar teste
        drive_service.files().delete(fileId=file['id']).execute()
        
    except Exception as e:
        print(f"❌ Erro de escrita: {e}")

if __name__ == '__main__':
    check_drive_permission()