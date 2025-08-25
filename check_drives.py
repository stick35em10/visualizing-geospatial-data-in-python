import os
import json
import base64
import io
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

def check_drive_permissio():
    """Verifica se tem permissão no Shared Drive"""
    print("🔍 Verificando permissões do Drive...")
    
    try:
        # Obter credenciais
        creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
        if not creds_json:
            print("❌ Variável GOOGLE_SHEETS_CREDENTIALS não encontrada")
            return False
            
        creds_json = creds_json.strip()
        if creds_json.startswith('eyJ'):
            creds_json = base64.b64decode(creds_json).decode('utf-8')
        
        creds_dict = json.loads(creds_json)
        credentials = Credentials.from_service_account_info(creds_dict)
        
        # Criar serviço
        drive_service = build('drive', 'v3', credentials=credentials)
        
        SHARED_DRIVE_ID = '1T3bLqnSCLg3_zkqnj5JXzH8tvN-h63yy'
        
        # 1. Verificar se o Shared Drive existe e é acessível
        try:
            drive_info = drive_service.drives().get(driveId=SHARED_DRIVE_ID).execute()
            print(f"✅ Shared Drive encontrado: {drive_info.get('name')}")
        except Exception as e:
            print(f"❌ Erro ao acessar Shared Drive: {e}")
            return False
        
        # 2. Tentar criar um arquivo de teste
        try:
            file_metadata = {
                'name': 'test_permission.txt',
                'parents': [SHARED_DRIVE_ID],
                'mimeType': 'text/plain'
            }
            
            media = MediaIoBaseUpload(
                io.BytesIO(b'Teste de permissão'),
                mimetype='text/plain'
            )
            
            file = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                supportsAllDrives=True,
                fields='id, name'
            ).execute()
            
            print(f"✅ Permissão de escrita OK! Arquivo criado: {file.get('name')} (ID: {file.get('id')})")
            
            # Limpar teste
            drive_service.files().delete(fileId=file['id']).execute()
            print("✅ Arquivo de teste removido")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro ao criar arquivo teste: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Erro geral: {e}")
        return False

if __name__ == '__main__':
    check_drive_permissio()