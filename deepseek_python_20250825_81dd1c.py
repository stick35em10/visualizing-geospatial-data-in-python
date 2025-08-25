import os
import json
import base64
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io

def test_drive_permissions():
    try:
        # Obter credenciais (mesmo código do seu app)
        creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
        if not creds_json:
            print("❌ Variável GOOGLE_SHEETS_CREDENTIALS não encontrada")
            return False
        
        creds_json = creds_json.strip()
        if creds_json.startswith('eyJ'):
            creds_json = base64.b64decode(creds_json).decode('utf-8')
        
        creds_dict = json.loads(creds_json)
        
        # Scopes com permissão de escrita
        scopes = [
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/spreadsheets'
        ]
        
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        
        # Criar serviço do Drive
        drive_service = build('drive', 'v3', credentials=credentials)
        
        # Testar listagem de arquivos (verificação básica de permissão)
        results = drive_service.files().list(
            pageSize=10, 
            fields="files(id, name)"
        ).execute()
        
        files = results.get('files', [])
        print(f"✅ Conectado ao Drive. {len(files)} arquivos encontrados.")
        
        # Testar criação de um arquivo de teste
        file_metadata = {
            'name': 'test_permission.txt',
            'mimeType': 'text/plain'
        }
        
        media = MediaIoBaseUpload(
            io.BytesIO(b"Teste de permissão do Drive"),
            mimetype='text/plain',
            resumable=True
        )
        
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        print(f"✅ Arquivo de teste criado com ID: {file.get('id')}")
        
        # Limpar - deletar arquivo de teste
        drive_service.files().delete(fileId=file.get('id')).execute()
        print("✅ Arquivo de teste deletado.")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao testar permissões do Drive: {str(e)}")
        return False

if __name__ == "__main__":
    test_drive_permissions()