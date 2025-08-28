import os
import json
import logging
import base64

from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials
from google.auth.exceptions import GoogleAuthError

#fazer upload das imagens e depois poder visualizá-las
import uuid
import io
from PIL import Image
import requests
from googleapiclient.http import MediaIoBaseUpload
#####
from deepseek_python_20250825_81dd1c import test_drive_permissions
test_drive_permissions()

from check_drive import check_drive_permission
check_drive_permission()

# Adicione as importações do Cloudinary:
# Adicione após as outras importações
import re  # Adicione esta linha com as outras importações
import cloudinary
import cloudinary.uploader
import cloudinary.api
from cloudinary.utils import cloudinary_url

# Configure o Cloudinary (após as configurações do Flask):
# Configuração do Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True
)

#import re
import unicodedata
from urllib.parse import quote

def sanitize_filename(filename):
    """
    Sanitize filename for Cloudinary upload
    - Remove or replace special characters
    - Convert accented characters to ASCII
    - Replace spaces with underscores
    """
    # Normalize unicode characters (convert accents to ASCII)
    filename = unicodedata.normalize('NFD', filename)
    filename = ''.join(char for char in filename if unicodedata.category(char) != 'Mn')
    
    # Convert to lowercase
    filename = filename.lower()
    
    # Replace spaces and special characters with underscores
    filename = re.sub(r'[^\w\-_\.]', '_', filename)
    
    # Remove multiple consecutive underscores
    filename = re.sub(r'_+', '_', filename)
    
    # Remove leading/trailing underscores
    filename = filename.strip('_')
    
    return filename

def upload_to_cloudinary(file_content, original_filename):
    """Upload file to Cloudinary with proper URL generation"""
    try:
        # Sanitize the filename
        sanitized_filename = sanitize_filename(original_filename)
        
        # Create a unique identifier
        unique_id = str(uuid.uuid4())[:8]
        
        # Get current date for folder organization
        current_date = datetime.now().strftime('%Y%m%d')
        
        # Create the public_id (path in Cloudinary)
        public_id = f"sheets_app/{current_date}/{unique_id}_{sanitized_filename}"
        
        # Remove file extension from public_id (Cloudinary adds it automatically)
        public_id = public_id.rsplit('.', 1)[0]
        
        log_step("CLOUDINARY_UPLOAD", f"Uploading with public_id: {public_id}")
        
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file_content,
            public_id=public_id,
            folder="sheets_app",  # This will be part of the public_id
            resource_type="auto",
            overwrite=True,
            quality="auto",
            fetch_format="auto"
        )
        
        # Get the secure URL (HTTPS)
        image_url = upload_result.get('secure_url')
        
        if not image_url:
            raise Exception("Cloudinary não retornou URL da imagem")
        
        log_step("CLOUDINARY_UPLOAD", f"✅ Upload concluído: {image_url}")
        
        return image_url
        
    except Exception as e:
        log_step("CLOUDINARY_UPLOAD", f"❌ Erro no upload: {str(e)}", False)
        raise Exception(f"Erro no upload para Cloudinary: {str(e)}")

#upload_to_cloudinary(file_content, original_filename):
# Substitua a função upload_to_drive por uma função para o Cloudinary:
"""
def upload_to_cloudinary(file_content, filename):
    ""Faz upload de um arquivo para o Cloudinary e retorna a URL""
    try:
        # Upload para o Cloudinary
        upload_result = cloudinary.uploader.upload(
            file_content,
            public_id=f"sheets_app/{datetime.now().strftime('%Y%m%d')}/{uuid.uuid4().hex[:8]}_{filename}",
            resource_type="auto"
        )
        
        # URL otimizada (formato automático e qualidade automática)
        optimize_url, _ = cloudinary_url(
            upload_result['public_id'],
            fetch_format="auto",
            quality="auto"
        )
        
        log_step("CLOUDINARY_UPLOAD", f"✅ Upload realizado: {filename} -> {optimize_url}")
        return optimize_url
        
    except Exception as e:
        error_msg = f"❌ Erro no upload para Cloudinary: {str(e)}"
        log_step("CLOUDINARY_UPLOAD", error_msg, False)
        raise Exception(error_msg)

"""
def upload_to_cloudinary_advanced(file_content, filename):
    """Upload avançado para Cloudinary com otimizações"""
    try:
        # Upload com otimizações
        upload_result = cloudinary.uploader.upload(
            file_content,
            public_id=f"sheets_app/{datetime.now().strftime('%Y%m%d')}/{uuid.uuid4().hex[:8]}_{filename}",
            resource_type="auto",
            quality="auto",
            fetch_format="auto",
            transformation=[
                {'width': 1200, 'height': 1200, 'crop': 'limit'},  # Tamanho máximo
                {'quality': 'auto'},
                {'format': 'auto'}
            ]
        )
        
        # URL para exibição (pode adicionar mais transformações se quiser)
        display_url, _ = cloudinary_url(
            upload_result['public_id'],
            width=800,
            height=600,
            crop="fill",
            quality="auto",
            format="auto"
        )
        
        log_step("CLOUDINARY_UPLOAD", f"✅ Upload avançado: {filename}")
        return display_url
        
    except Exception as e:
        error_msg = f"❌ Erro no upload avançado: {str(e)}"
        log_step("CLOUDINARY_UPLOAD", error_msg, False)
        raise Exception(error_msg)
    
#from check_drives import check_drive_permissio
#check_drive_permissio()

#from check_drive import check_drive_permission
# Configuração de logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Apenas console no Render
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

CORS(app, resources={
    r"/*": {
        "origins": [
            "https://stick35em10.github.io",
            "http://localhost:*",
            "http://127.0.0.1:*"
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": True,
        "max_age": 3600
    }
})

# Variáveis globais para status e cache
sheets_status = {
    'initialized': False,
    'credentials_found': False,
    'authentication_ok': False,
    'spreadsheet_accessible': False,
    'error_messages': [],
    'last_test_time': None
}

# Cache global para evitar reconexões desnecessárias
_client_cache = None
_spreadsheet_cache = None

# Adicione esta constante no início do arquivo (substitua pelo ID real)
SHARED_DRIVE_ID = '1T3bLqnSCLg3_zkqnj5JXzH8tvN-h63yy'

def create_shared_folder():
    """Cria uma pasta compartilhada no Google Drive para armazenar as imagens"""
    try:
        drive_service = get_drive_service()
        
        # ID do Shared Drive (você precisa obter este ID)
        SHARED_DRIVE_ID = "YOUR_SHARED_DRIVE_ID_HERE"
        
        folder_name = f"SheetsApp_Images_{datetime.now().strftime('%Y%m%d')}"
        
        # Verificar se a pasta já existe no Shared Drive
        results = drive_service.files().list(
            q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            driveId=SHARED_DRIVE_ID,
            corpora='drive',
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
            fields="files(id, name)"
        ).execute()
        
        files = results.get('files', [])
        
        if files:
            folder_id = files[0]['id']
            log_step("DRIVE_FOLDER", f"✅ Pasta existente encontrada: {folder_id}")
        else:
            # Criar nova pasta no Shared Drive
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [SHARED_DRIVE_ID]
            }
            
            folder = drive_service.files().create(
                body=folder_metadata,
                fields='id, name',
                supportsAllDrives=True
            ).execute()
            
            folder_id = folder.get('id')
            log_step("DRIVE_FOLDER", f"✅ Nova pasta criada no Shared Drive: {folder_name} ({folder_id})")
        
        return folder_id
        
    except Exception as e:
        log_step("DRIVE_FOLDER", f"❌ Erro ao criar/encontrar pasta: {str(e)}", False)
        return None

def upload_to_drive(file_content, filename, mime_type):
    """Upload de arquivo para o Google Drive com Shared Drive support"""
    try:
        drive_service = get_drive_service()
        
        # Criar ou obter pasta
        folder_id = create_shared_folder()
        
        # Sanitizar nome do arquivo
        safe_filename = re.sub(r'[^\w\.-]', '_', filename)
        unique_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}_{safe_filename}"
        
        # Metadados do arquivo
        file_metadata = {
            'name': unique_filename,
            'mimeType': mime_type
        }
        
        # Se temos uma pasta, usar ela como parent
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        # Upload do arquivo
        media = MediaIoBaseUpload(
            io.BytesIO(file_content),
            mimetype=mime_type,
            resumable=True
        )
        
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink, webContentLink, parents',
            supportsAllDrives=True
        ).execute()
        
        file_id = file.get('id')
        
        # URL direta para visualização
        file_url = f"https://drive.google.com/uc?id={file_id}"
        
        log_step("DRIVE_UPLOAD", f"✅ Upload realizado no Shared Drive: {unique_filename} -> {file_url}")
        return file_url, file_id, unique_filename
            
    except HttpError as e:
        if 'storageQuotaExceeded' in str(e):
            raise Exception("Quota de armazenamento excedida. Verifique o Shared Drive.")
        else:
            raise Exception(f"Erro HTTP do Drive: {e.resp.status} - {str(e)}")
    
    except Exception as e:
        raise Exception(f"Erro no upload: {str(e)}")


def log_step(step, message, success=True):
    """Registra cada passo com timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    level = "INFO" if success else "ERROR"
    log_message = f"[{timestamp}] {step}: {message}"
    
    if success:
        logger.info(log_message)
    else:
        logger.error(log_message)
        sheets_status['error_messages'].append(log_message)
    
    return log_message

def get_sheets_client():
    """Retorna cliente do Google Sheets com cache"""
    global _client_cache, _spreadsheet_cache
    
    try:
        # Verifica se já temos um cliente em cache
        if _client_cache is not None:
            return _client_cache, _spreadsheet_cache
        
        # Parse das credenciais
        creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
        if not creds_json:
            raise Exception("Variável GOOGLE_SHEETS_CREDENTIALS não encontrada")
        
        # Remove possíveis espaços ou quebras de linha
        creds_json = creds_json.strip()
        
        # Tenta decodificar se estiver em base64
        try:
            if creds_json.startswith('eyJ'):
                creds_json = base64.b64decode(creds_json).decode('utf-8')
        except:
            pass
        
        # Parse do JSON
        creds_dict = json.loads(creds_json)
        
        # Configuração do escopo
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            #'https://www.googleapis.com/auth/drive.readonly'
            'https://www.googleapis.com/auth/drive',  # ← PERMISSÃO COMPLETA (escrita)
            # 'https://www.googleapis.com/auth/drive.file'  # ← Permissão apenas para arquivos criados pela app
        ]
        
        # Criar credenciais
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        
        # Autorizar cliente gspread
        client = gspread.authorize(credentials)
        
        # Abrir planilha
        spreadsheet_id = os.getenv('SPREADSHEET_ID')
        if not spreadsheet_id:
            raise Exception("Variável SPREADSHEET_ID não encontrada")
        
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        # Cache dos objetos
        _client_cache = client
        _spreadsheet_cache = spreadsheet
        
        log_step("SHEETS_CLIENT", f"✅ Cliente conectado à planilha: {spreadsheet.title}")
        
        return client, spreadsheet
        
    except Exception as e:
        log_step("SHEETS_CLIENT", f"❌ Erro ao conectar: {str(e)}", False)
        raise

def check_environment_variables():
    """Verifica se as variáveis de ambiente estão definidas"""
    log_step("ENV_CHECK", "🔍 Verificando variáveis de ambiente...")
    
    required_vars = ['GOOGLE_SHEETS_CREDENTIALS', 'SPREADSHEET_ID']
    missing_vars = []
    found_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            found_vars.append(var)
            preview = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
            log_step("ENV_CHECK", f"✅ {var} encontrada: {preview}")
        else:
            missing_vars.append(var)
            log_step("ENV_CHECK", f"❌ {var} NÃO ENCONTRADA", False)
    
    return {
        'found_vars': found_vars,
        'missing_vars': missing_vars,
        'all_found': len(missing_vars) == 0
    }

def parse_credentials():
    """Tenta fazer parse das credenciais JSON"""
    log_step("CREDENTIALS_PARSE", "🔐 Fazendo parse das credenciais...")
    
    try:
        creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
        if not creds_json:
            raise Exception("Variável GOOGLE_SHEETS_CREDENTIALS não encontrada")
        
        creds_json = creds_json.strip()
        
        try:
            if creds_json.startswith('eyJ'):
                creds_json = base64.b64decode(creds_json).decode('utf-8')
                log_step("CREDENTIALS_PARSE", "Credenciais decodificadas de base64")
        except:
            pass
        
        creds_dict = json.loads(creds_json)
        
        required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email', 'client_id', 'auth_uri', 'token_uri']
        missing_fields = [field for field in required_fields if field not in creds_dict]
        
        if missing_fields:
            raise Exception(f"Campos obrigatórios ausentes: {missing_fields}")
        
        if creds_dict.get('type') != 'service_account':
            raise Exception(f"Tipo de credencial inválido: {creds_dict.get('type')}")
        
        log_step("CREDENTIALS_PARSE", f"✅ Credenciais válidas! Projeto: {creds_dict.get('project_id')}")
        sheets_status['credentials_found'] = True
        
        return {
            'success': True,
            'project_id': creds_dict.get('project_id'),
            'client_email': creds_dict.get('client_email'),
            'credentials': creds_dict
        }
        
    except json.JSONDecodeError as e:
        error_msg = f"❌ Erro ao fazer parse do JSON: {str(e)}"
        log_step("CREDENTIALS_PARSE", error_msg, False)
        return {'success': False, 'error': error_msg, 'type': 'json_parse_error'}
    
    except Exception as e:
        error_msg = f"❌ Erro nas credenciais: {str(e)}"
        log_step("CREDENTIALS_PARSE", error_msg, False)
        return {'success': False, 'error': error_msg, 'type': 'credentials_error'}

def test_google_sheets_connection():
    """Testa a conexão completa com o Google Sheets"""
    log_step("SHEETS_CONNECTION", "📊 Testando conexão com Google Sheets...")
    
    try:
        client, spreadsheet = get_sheets_client()
        
        # Listar abas da planilha
        worksheets = spreadsheet.worksheets()
        worksheet_names = [ws.title for ws in worksheets]
        log_step("SHEETS_CONNECTION", f"📄 Abas encontradas: {worksheet_names}")
        
        # Testar leitura da primeira aba
        if worksheets:
            first_sheet = worksheets[0]
            try:
                sample_data = first_sheet.get('A1:E5')
                log_step("SHEETS_CONNECTION", f"✅ Teste de leitura OK. {len(sample_data)} linhas encontradas")
            except Exception as read_error:
                log_step("SHEETS_CONNECTION", f"⚠️ Aviso: Erro ao ler dados: {read_error}")
        
        sheets_status['spreadsheet_accessible'] = True
        sheets_status['initialized'] = True
        sheets_status['authentication_ok'] = True
        sheets_status['last_test_time'] = datetime.now().isoformat()
        
        return {
            'success': True,
            'spreadsheet_id': os.getenv('SPREADSHEET_ID'),
            'spreadsheet_title': spreadsheet.title,
            'worksheet_names': worksheet_names,
            'test_time': sheets_status['last_test_time']
        }
        
    except Exception as e:
        error_msg = f"❌ Erro de conexão: {str(e)}"
        log_step("SHEETS_CONNECTION", error_msg, False)
        return {'success': False, 'error': error_msg}

# ================================
# ROTAS DE API PARA O CLIENTE HTML
# ================================

# Updated upload_photos route
@app.route('/api/upload/photos', methods=['POST', 'OPTIONS'])
def upload_photos():
    """Endpoint completo para upload de fotos com armazenamento no Cloudinary"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    log_step("UPLOAD_PHOTOS", "📸 Requisição de upload de fotos recebida")
    
    try:
        if not sheets_status['initialized']:
            sheets_result = test_google_sheets_connection()
            if not sheets_result.get('success', False):
                return jsonify({
                    'success': False,
                    'error': 'Erro de autenticação com o Google Sheets'
                }), 500
        
        # Obter dados do formulário
        title = request.form.get('title', 'Foto sem título')
        description = request.form.get('description', '')
        worksheet_name = request.form.get('worksheet', 'Imagens')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        accuracy = request.form.get('accuracy')
        
        # Processar arquivos
        uploaded_files = request.files.getlist('photos')
        file_count = len(uploaded_files)
        
        if file_count == 0:
            return jsonify({
                'success': False,
                'error': 'Nenhum arquivo enviado'
            }), 400
        
        log_step("UPLOAD_PHOTOS", f"Processando {file_count} arquivo(s) para a aba '{worksheet_name}'")
        log_step("UPLOAD_PHOTOS", f"Arquivos recebidos: {[f.filename for f in uploaded_files]}")
        
        client, spreadsheet = get_sheets_client()
        
        # Verificar se a worksheet existe, se não, criar
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows="1000", cols="15")
            # Adicionar cabeçalhos
            headers = [
                "Data", "Título", "Descrição", "Latitude", "Longitude", 
                "Precisão", "Nome do Arquivo Original", "Nome Sanitizado", "Tamanho", "Tipo", 
                "URL da Imagem", "ID Único", "Largura", "Altura", "Formato"
            ]
            worksheet.append_row(headers)
            log_step("UPLOAD_PHOTOS", f"✅ Nova worksheet criada: {worksheet_name}")
        
        # Processar cada arquivo
        results = []
        successful_uploads = 0
        failed_uploads = 0
        
        for i, file in enumerate(uploaded_files):
            if file and file.filename:
                try:
                    # Ler o arquivo
                    file_content = file.read()
                    filename = file.filename
                    sanitized_filename = sanitize_filename(filename)
                    file_size = len(file_content)
                    unique_id = str(uuid.uuid4())[:8]
                    
                    log_step("UPLOAD_PHOTOS", f"Processando arquivo {i+1}: {filename} -> {sanitized_filename} ({file_size} bytes)")
                    
                    # Verificar tamanho do arquivo (limite de 10MB para Cloudinary)
                    if file_size > 10 * 1024 * 1024:
                        raise Exception(f"Arquivo muito grande: {file_size} bytes (limite: 10MB)")
                    
                    # Processar a imagem para obter metadados
                    try:
                        image = Image.open(io.BytesIO(file_content))
                        width, height = image.size
                        image_format = image.format
                        log_step("UPLOAD_PHOTOS", f"Imagem processada: {width}x{height}, formato: {image_format}")
                    
                    except Exception as img_error:
                        log_step("UPLOAD_PHOTOS", f"⚠️ Aviso: Erro ao processar imagem: {img_error}")
                        width, height, image_format = 0, 0, 'Desconhecido'
                        
                    # Fazer upload para o Cloudinary
                    log_step("UPLOAD_PHOTOS", f"Iniciando upload para Cloudinary: {filename}")
                    image_url = upload_to_cloudinary(file_content, filename)
                    
                    # Preparar dados para a planilha
                    row_data = [
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        title,
                        description,
                        latitude or '',
                        longitude or '',
                        accuracy or '',
                        filename,  # Nome original
                        sanitized_filename,  # Nome sanitizado
                        file_size,
                        file.content_type,
                        image_url,
                        unique_id,
                        width,
                        height,
                        image_format
                    ]
                    
                    # Adicionar à planilha
                    worksheet.append_row(row_data)
                    
                    results.append({
                        'filename': filename,
                        'sanitized_filename': sanitized_filename,
                        'size': file_size,
                        'type': file.content_type,
                        'url': image_url,
                        'id': unique_id,
                        'dimensions': f"{width}x{height}",
                        'status': 'success'
                    })
                    
                    successful_uploads += 1
                    log_step("UPLOAD_PHOTOS", f"✅ Arquivo {i+1}/{file_count} processado: {filename} -> {image_url}")
                    
                except Exception as file_error:
                    failed_uploads += 1
                    error_msg = f"Erro ao processar {filename}: {str(file_error)}"
                    log_step("UPLOAD_PHOTOS", error_msg, False)
                    results.append({
                        'filename': filename,
                        'status': 'error',
                        'error': str(file_error)
                    })
        
        return jsonify({
            'success': True,
            'message': f'{file_count} arquivo(s) processado(s)!',
            'results': results,
            'summary': {
                'total_files': file_count,
                'successful': successful_uploads,
                'failed': failed_uploads,
                'worksheet': worksheet_name
            },
            'spreadsheet_title': spreadsheet.title
        })
        
    except Exception as e:
        error_msg = f"⚠ Erro no upload de fotos: {str(e)}"
        log_step("UPLOAD_PHOTOS", error_msg, False)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500



"""
@app.route('/api/upload/photos', methods=['POST', 'OPTIONS'])
def upload_photos():
    ""Endpoint completo para upload de fotos com armazenamento no Cloudinary""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    log_step("UPLOAD_PHOTOS", "📸 Requisição de upload de fotos recebida")
    
    try:
        if not sheets_status['initialized']:
            sheets_result = test_google_sheets_connection()
            if not sheets_result.get('success', False):
                return jsonify({
                    'success': False,
                    'message': 'Erro de autenticação com o Google Sheets'
                }), 500
        
        # Obter dados do formulário
        title = request.form.get('title', 'Foto sem título')
        description = request.form.get('description', '')
        worksheet_name = request.form.get('worksheet', 'Imagens')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        accuracy = request.form.get('accuracy')
        
        # Processar arquivos
        uploaded_files = request.files.getlist('photos')
        file_count = len(uploaded_files)
        
        if file_count == 0:
            return jsonify({
                'success': False,
                'message': 'Nenhum arquivo enviado'
            }), 400
        
        log_step("UPLOAD_PHOTOS", f"Processando {file_count} arquivo(s) para a aba '{worksheet_name}'")
        log_step("UPLOAD_PHOTOS", f"Arquivos recebidos: {[f.filename for f in uploaded_files]}")
        
        client, spreadsheet = get_sheets_client()
        
        # Verificar se a worksheet existe, se não, criar
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows="1000", cols="15")
            # Adicionar cabeçalhos
            headers = [
                "Data", "Título", "Descrição", "Latitude", "Longitude", 
                "Precisão", "Nome do Arquivo", "Tamanho", "Tipo", 
                "URL da Imagem", "ID Único", "Largura", "Altura", "Formato"
            ]
            worksheet.append_row(headers)
            log_step("UPLOAD_PHOTOS", f"✅ Nova worksheet criada: {worksheet_name}")
        
        # Processar cada arquivo
        results = []
        for i, file in enumerate(uploaded_files):
            if file and file.filename:
                try:
                    # Ler o arquivo
                    file_content = file.read()
                    filename = file.filename
                    file_size = len(file_content)
                    unique_id = str(uuid.uuid4())[:8]
                    
                    log_step("UPLOAD_PHOTOS", f"Processando arquivo {i+1}: {filename} ({file_size} bytes)")
                    
                    # Verificar tamanho do arquivo (limite de 5MB)
                    if file_size > 5 * 1024 * 1024:
                        raise Exception(f"Arquivo muito grande: {file_size} bytes (limite: 5MB)")
                    
                    # Processar a imagem para obter metadados
                    try:
                        image = Image.open(io.BytesIO(file_content))
                        width, height = image.size
                        image_format = image.format
                        log_step("UPLOAD_PHOTOS", f"Imagem processada: {width}x{height}, formato: {image_format}")
                    
                    except Exception as img_error:
                        log_step("UPLOAD_PHOTOS", f"⚠️ Aviso: Erro ao processar imagem: {img_error}")
                        width, height, image_format = 0, 0, 'Desconhecido'
                        
                    # Fazer upload para o Cloudinary (SUBSTITUINDO O DRIVE)
                    log_step("UPLOAD_PHOTOS", f"Iniciando upload para Cloudinary: {filename}")
                    image_url = upload_to_cloudinary(file_content, filename)
                    
                    # Preparar dados para a planilha
                    row_data = [
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        title,
                        description,
                        latitude or '',
                        longitude or '',
                        accuracy or '',
                        filename,
                        file_size,
                        file.content_type,
                        image_url,  # URL do Cloudinary aqui
                        unique_id,
                        width,
                        height,
                        image_format
                    ]
                    
                    # Adicionar à planilha
                    worksheet.append_row(row_data)
                    
                    results.append({
                        'filename': filename,
                        'size': file_size,
                        'type': file.content_type,
                        'url': image_url,
                        'id': unique_id,
                        'dimensions': f"{width}x{height}",
                        'status': 'success'
                    })
                    
                    log_step("UPLOAD_PHOTOS", f"✅ Arquivo {i+1}/{file_count} processado: {filename} -> {image_url}")
                    
                except Exception as file_error:
                    error_msg = f"Erro ao processar {filename}: {str(file_error)}"
                    log_step("UPLOAD_PHOTOS", error_msg, False)
                    results.append({
                        'filename': filename,
                        'status': 'error',
                        'error': str(file_error)
                    })
        
        return jsonify({
            'success': True,
            'message': f'{file_count} arquivo(s) processado(s) com sucesso!',
            'results': results,
            'worksheet': worksheet_name,
            'spreadsheet_title': spreadsheet.title,
            'uploaded_count': len([r for r in results if r['status'] == 'success'])
        })
        
    except Exception as e:
        error_msg = f"❌ Erro no upload de fotos: {str(e)}"
        log_step("UPLOAD_PHOTOS", error_msg, False)
        return jsonify({
            'success': False,
            'message': 'Erro no processamento do upload',
            'error': str(e)
        }), 500

"""
# Adicione esta função para debug
@app.route('/debug/cloudinary', methods=['GET'])
def debug_cloudinary():
    """Testa a configuração do Cloudinary"""
    try:
        # Verificar se as variáveis de ambiente estão definidas
        cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
        api_key = os.getenv('CLOUDINARY_API_KEY')
        api_secret = os.getenv('CLOUDINARY_API_SECRET')
        
        return jsonify({
            'cloudinary_configured': all([cloud_name, api_key, api_secret]),
            'cloud_name': cloud_name,
            'api_key': api_key[:10] + '...' if api_key else None,
            'api_secret': api_secret[:10] + '...' if api_secret else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
            
@app.route('/debug/service-account-info', methods=['GET'])
def debug_service_account_info():
    """Retorna o email du service account para configurar no Shared Drive"""
    try:
        creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
        if not creds_json:
            return jsonify({'error': 'Credenciais não encontradas'}), 500
        
        creds_json = creds_json.strip()
        if creds_json.startswith('eyJ'):
            creds_json = base64.b64decode(creds_json).decode('utf-8')
        
        creds_dict = json.loads(creds_json)
        
        return jsonify({
            'service_account_email': creds_dict.get('client_email'),
            'project_id': creds_dict.get('project_id'),
            'instructions': 'Adicione este email como membro do Shared Drive com permissão de Editor'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sheets/worksheets', methods=['GET'])
def get_worksheets():
    """Lista todas as abas/worksheets da planilha"""
    log_step("API_WORKSHEETS", "Requisição para listar worksheets")
    
    try:
        client, spreadsheet = get_sheets_client()
        worksheets = spreadsheet.worksheets()
        worksheet_list = []
        
        for ws in worksheets:
            worksheet_list.append({
                'id': ws.id,
                'title': ws.title,
                'index': ws.index,
                'row_count': ws.row_count,
                'col_count': ws.col_count
            })
        
        return jsonify({
            'success': True,
            'worksheets': worksheet_list,
            'spreadsheet_title': spreadsheet.title
        })
        
    except Exception as e:
        error_msg = f"Erro ao listar worksheets: {str(e)}"
        log_step("API_WORKSHEETS", error_msg, False)
        return jsonify({'success': False, 'error': error_msg}), 500

@app.route('/api/sheets/data', methods=['GET'])
def get_sheet_data():
    """Retorna os dados de uma worksheet específica"""
    log_step("API_DATA", "Requisição para obter dados da planilha")
    
    try:
        # Parâmetros da query
        worksheet_name = request.args.get('worksheet', '')
        start_row = int(request.args.get('start_row', 1))
        max_rows = request.args.get('max_rows', 'all')
        
        client, spreadsheet = get_sheets_client()
        
        # Seleciona a worksheet
        if worksheet_name:
            try:
                worksheet = spreadsheet.worksheet(worksheet_name)
            except gspread.exceptions.WorksheetNotFound:
                return jsonify({
                    'success': False,
                    'error': f'Worksheet "{worksheet_name}" não encontrada'
                }), 404
        else:
            worksheet = spreadsheet.sheet1  # Primeira aba por padrão
        
        log_step("API_DATA", f"Obtendo dados da worksheet: {worksheet.title}")
        
        # Obter todos os registros
        try:
            # Usa get_all_records para obter dados como lista de dicionários
            all_records = worksheet.get_all_records()
            
            # Se não há registros, tenta obter valores brutos
            if not all_records:
                all_values = worksheet.get_all_values()
                if all_values:
                    # Primeira linha como headers
                    headers = all_values[0] if all_values else []
                    data_rows = all_values[1:] if len(all_values) > 1 else []
                    
                    # Converte para lista de dicionários
                    all_records = []
                    for row in data_rows:
                        record = {}
                        for i, header in enumerate(headers):
                            value = row[i] if i < len(row) else ''
                            record[header] = value
                        all_records.append(record)
            
            # Aplicar filtros se necessário
            if max_rows != 'all':
                max_rows = int(max_rows)
                all_records = all_records[:max_rows]
            
            # Estatísticas
            total_rows = len(all_records)
            total_columns = len(all_records[0].keys()) if all_records else 0
            
            log_step("API_DATA", f"✅ Dados obtidos: {total_rows} linhas, {total_columns} colunas")
            
            return jsonify({
                'success': True,
                'data': all_records,
                'metadata': {
                    'worksheet_name': worksheet.title,
                    'total_rows': total_rows,
                    'total_columns': total_columns,
                    'spreadsheet_title': spreadsheet.title,
                    'last_update': datetime.now().isoformat()
                }
            })
            
        except Exception as data_error:
            log_step("API_DATA", f"❌ Erro ao ler dados: {str(data_error)}", False)
            return jsonify({
                'success': False,
                'error': f'Erro ao ler dados da worksheet: {str(data_error)}'
            }), 500
        
    except Exception as e:
        error_msg = f"Erro interno ao obter dados: {str(e)}"
        log_step("API_DATA", error_msg, False)
        return jsonify({'success': False, 'error': error_msg}), 500

@app.route('/api/sheets/info', methods=['GET'])
def get_sheet_info():
    """Retorna informações gerais sobre a planilha"""
    log_step("API_INFO", "Requisição para informações da planilha")
    
    try:
        client, spreadsheet = get_sheets_client()
        worksheets = spreadsheet.worksheets()
        
        sheet_info = {
            'spreadsheet_id': spreadsheet.id,
            'spreadsheet_title': spreadsheet.title,
            'spreadsheet_url': spreadsheet.url,
            'total_worksheets': len(worksheets),
            'worksheets': []
        }
        
        for ws in worksheets:
            sheet_info['worksheets'].append({
                'id': ws.id,
                'title': ws.title,
                'index': ws.index,
                'row_count': ws.row_count,
                'col_count': ws.col_count
            })
        
        return jsonify({
            'success': True,
            'info': sheet_info
        })
        
    except Exception as e:
        error_msg = f"Erro ao obter informações: {str(e)}"
        log_step("API_INFO", error_msg, False)
        return jsonify({'success': False, 'error': error_msg}), 500

# ================================
# ROTAS DE DEBUG ORIGINAIS
# ================================



@app.route('/debug/environment', methods=['GET'])
def debug_environment():
    """Endpoint para verificar variáveis de ambiente"""
    log_step("DEBUG_ENV", "Requisição de debug de ambiente recebida")
    env_check = check_environment_variables()
    
    system_info = {
        'python_version': os.sys.version,
        'current_time': datetime.now().isoformat(),
        'working_directory': os.getcwd(),
        'environment_variables': env_check,
    }
    
    return jsonify(system_info)

@app.route('/debug/credentials', methods=['GET'])
def debug_credentials():
    """Endpoint para testar parse das credenciais"""
    log_step("DEBUG_CREDS", "Requisição de debug de credenciais recebida")
    creds_result = parse_credentials()
    
    if creds_result['success']:
        safe_result = {
            'success': True,
            'project_id': creds_result.get('project_id'),
            'client_email': creds_result.get('client_email'),
            'message': 'Credenciais parseadas com sucesso'
        }
    else:
        safe_result = {
            'success': False,
            'error': creds_result['error'],
            'type': creds_result.get('type', 'unknown_error'),
            'suggestions': []
        }
        
        if creds_result.get('type') == 'json_parse_error':
            safe_result['suggestions'] = [
                'Verifique se o JSON está bem formatado',
                'Certifique-se de que não há quebras de linha extras',
                'Tente recriar a variável de ambiente no Render'
            ]
    
    return jsonify(safe_result)

@app.route('/debug/sheets', methods=['GET'])
def debug_sheets():
    """Endpoint para testar conexão completa com Google Sheets"""
    log_step("DEBUG_SHEETS", "Requisição de debug do Google Sheets recebida")
    result = test_google_sheets_connection()
    return jsonify(result)

@app.route('/debug/full', methods=['GET'])
def debug_full():
    """Endpoint para verificação completa passo a passo"""
    log_step("DEBUG_FULL", "🚀 Iniciando verificação completa...")
    
    # Reset do status e cache
    global sheets_status, _client_cache, _spreadsheet_cache
    sheets_status = {
        'initialized': False,
        'credentials_found': False,
        'authentication_ok': False,
        'spreadsheet_accessible': False,
        'error_messages': [],
        'last_test_time': None
    }
    _client_cache = None
    _spreadsheet_cache = None
    
    start_time = datetime.now()
    
    # Passo 1: Variáveis de ambiente
    log_step("DEBUG_FULL", "📋 Passo 1: Verificando ambiente...")
    env_result = check_environment_variables()
    
    # Passo 2: Parse das credenciais
    log_step("DEBUG_FULL", "🔐 Passo 2: Validando credenciais...")
    creds_result = parse_credentials()
    
    # Passo 3: Conexão com Google Sheets
    log_step("DEBUG_FULL", "📊 Passo 3: Testando Google Sheets...")
    sheets_result = test_google_sheets_connection()
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    overall_success = (
        env_result['all_found'] and 
        creds_result['success'] and 
        sheets_result.get('success', False)
    )
    
    full_result = {
        'timestamp': end_time.isoformat(),
        'duration_seconds': duration,
        'steps': {
            '1_environment': env_result,
            '2_credentials': creds_result,
            '3_sheets_connection': sheets_result
        },
        'overall_status': sheets_status,
        'success': overall_success,
        'summary': {
            'environment_ok': env_result['all_found'],
            'credentials_ok': creds_result['success'],
            'sheets_ok': sheets_result.get('success', False),
            'ready_for_api': overall_success
        }
    }
    
    if overall_success:
        log_step("DEBUG_FULL", f"🎉 Verificação completa SUCESSO em {duration:.2f}s")
    else:
        log_step("DEBUG_FULL", f"❌ Verificação completa FALHOU em {duration:.2f}s", False)
    
    return jsonify(full_result)

@app.route('/debug/test-write', methods=['GET'])
def debug_test_write():
    """Testa escrita na planilha"""
    log_step("DEBUG_WRITE", "Testando escrita na planilha...")
    
    try:
        client, spreadsheet = get_sheets_client()
        worksheet = spreadsheet.sheet1
        
        test_data = [
            f"Teste: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "Dados de teste",
            "Status: OK"
        ]
        
        values = worksheet.get_all_values()
        next_row = len(values) + 1
        
        worksheet.update(f'A{next_row}:C{next_row}', [test_data])
        log_step("DEBUG_WRITE", f"✅ Dados escritos na linha {next_row}")
        
        return jsonify({
            'success': True,
            'message': f'Dados de teste escritos na linha {next_row}',
            'row': next_row,
            'data': test_data
        })
        
    except Exception as e:
        error_msg = f"Erro na escrita: {str(e)}"
        log_step("DEBUG_WRITE", error_msg, False)
        return jsonify({'success': False, 'error': error_msg}), 500

@app.route('/debug/status', methods=['GET'])
def debug_status():
    """Retorna o status atual da conexão"""
    return jsonify({
        'status': sheets_status,
        'current_time': datetime.now().isoformat(),
        'cache_info': {
            'client_cached': _client_cache is not None,
            'spreadsheet_cached': _spreadsheet_cache is not None
        }
    })

@app.route('/debug/clear-cache', methods=['GET'])
def debug_clear_cache():
    """Limpa o cache de conexão"""
    global _client_cache, _spreadsheet_cache
    _client_cache = None
    _spreadsheet_cache = None
    
    sheets_status['initialized'] = False
    sheets_status['spreadsheet_accessible'] = False
    
    log_step("DEBUG_CACHE", "🔄 Cache de conexão limpo")
    return jsonify({'success': True, 'message': 'Cache limpo'})

@app.route('/debug/check-drive', methods=['GET'])
def debug_check_drive():
    """Verifica permissões do Google Drive"""
    try:
        # Testar permissões do Drive
        drive_service = get_drive_service()
        
        # Tentar listar alguns arquivos
        results = drive_service.files().list(
            pageSize=5,
            fields="files(id, name, mimeType)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        files = results.get('files', [])
        
        return jsonify({
            'success': True,
            'drive_access': True,
            'files_found': len(files),
            'sample_files': files,
            'message': '✅ Acesso ao Google Drive verificado com sucesso'
        })
        
    except Exception as e:
        error_msg = f"❌ Erro no acesso ao Drive: {str(e)}"
        log_step("DEBUG_DRIVE", error_msg, False)
        return jsonify({
            'success': False,
            'drive_access': False,
            'error': error_msg
        }), 500

@app.route('/debug/test-shared-drive', methods=['GET'])
def debug_test_shared_drive():
    """Testa acesso ao Shared Drive"""
    try:
        drive_service = get_drive_service()
        
        # Listar Shared Drives
        drives = drive_service.drives().list(
            pageSize=10,
            fields="drives(id, name)"
        ).execute()
        
        shared_drives = drives.get('drives', [])
        
        # Verificar se temos acesso ao Shared Drive específico
        target_drive_id = SHARED_DRIVE_ID
        target_drive = None
        
        for drive in shared_drives:
            if drive['id'] == target_drive_id:
                target_drive = drive
                break
        
        if target_drive:
            # Tentar listar arquivos no Shared Drive
            results = drive_service.files().list(
                driveId=target_drive_id,
                corpora='drive',
                pageSize=5,
                fields="files(id, name, mimeType)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            
            files = results.get('files', [])
            
            return jsonify({
                'success': True,
                'shared_drive_access': True,
                'target_drive': target_drive,
                'files_in_drive': len(files),
                'sample_files': files,
                'message': f'✅ Acesso ao Shared Drive "{target_drive["name"]}" verificado'
            })
        else:
            return jsonify({
                'success': False,
                'shared_drive_access': False,
                'available_drives': [{'id': d['id'], 'name': d['name']} for d in shared_drives],
                'message': f'❌ Shared Drive com ID {target_drive_id} não encontrado'
            })
            
    except Exception as e:
        error_msg = f"❌ Erro no acesso ao Shared Drive: {str(e)}"
        log_step("DEBUG_SHARED_DRIVE", error_msg, False)
        return jsonify({
            'success': False,
            'shared_drive_access': False,
            'error': error_msg
        }), 500

# ================================
# ROTA PRINCIPAL E HEALTH CHECKS
# ================================

@app.route('/')
def home():
    """Página inicial com informações da API"""
    return jsonify({
        'message': '🚀 Sheets App API está funcionando!',
        'version': '1.0.0',
        'endpoints': {
            'debug': {
                '/debug/environment': 'Verificar variáveis de ambiente',
                '/debug/credentials': 'Testar credenciais',
                '/debug/sheets': 'Testar conexão com Google Sheets',
                '/debug/full': 'Verificação completa',
                '/debug/status': 'Status atual da conexão'
            },
            'api': {
                '/api/sheets/info': 'Informações da planilha',
                '/api/sheets/worksheets': 'Listar abas',
                '/api/sheets/data': 'Obter dados',
                '/api/upload/photos': 'Upload de fotos'
            }
        },
        'timestamp': datetime.now().isoformat()
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint de health check para o Render"""
    try:
        # Verificação básica de saúde
        env_ok = os.getenv('GOOGLE_SHEETS_CREDENTIALS') is not None
        sheets_ok = sheets_status.get('initialized', False)
        
        status = 'healthy' if (env_ok and sheets_ok) else 'degraded'
        
        return jsonify({
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'details': {
                'environment_configured': env_ok,
                'sheets_connected': sheets_ok,
                'last_test_time': sheets_status.get('last_test_time')
            }
        }), 200 if status == 'healthy' else 503
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

""" 
@app.route('/api/upload/photos', methods=['POST', 'OPTIONS'])
def upload_photos():
    ""Endpoint completo para upload de fotos com armazenamento no Cloudinary""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    log_step("UPLOAD_PHOTOS", "📸 Requisição de upload de fotos recebida")
    
    try:
        if not sheets_status['initialized']:
            sheets_result = test_google_sheets_connection()
            if not sheets_result.get('success', False):
                return jsonify({
                    'success': False,
                    'error': 'Erro de autenticação com o Google Sheets'
                }), 500
        
        # Obter dados do formulário
        title = request.form.get('title', 'Foto sem título')
        description = request.form.get('description', '')
        worksheet_name = request.form.get('worksheet', 'Imagens')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        accuracy = request.form.get('accuracy')
        
        # Processar arquivos
        uploaded_files = request.files.getlist('photos')
        file_count = len(uploaded_files)
        
        if file_count == 0:
            return jsonify({
                'success': False,
                'error': 'Nenhum arquivo enviado'
            }), 400
        
        log_step("UPLOAD_PHOTOS", f"Processando {file_count} arquivo(s) para a aba '{worksheet_name}'")
        log_step("UPLOAD_PHOTOS", f"Arquivos recebidos: {[f.filename for f in uploaded_files]}")
        
        client, spreadsheet = get_sheets_client()
        
        # Verificar se a worksheet existe, se não, criar
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows="1000", cols="15")
            # Adicionar cabeçalhos
            headers = [
                "Data", "Título", "Descrição", "Latitude", "Longitude", 
                "Precisão", "Nome do Arquivo", "Tamanho", "Tipo", 
                "URL da Imagem", "ID Único", "Largura", "Altura", "Formato"
            ]
            worksheet.append_row(headers)
            log_step("UPLOAD_PHOTOS", f"✅ Nova worksheet criada: {worksheet_name}")
        
        # Processar cada arquivo
        results = []
        successful_uploads = 0
        failed_uploads = 0
        
        for i, file in enumerate(uploaded_files):
            if file and file.filename:
                try:
                    # Ler o arquivo
                    file_content = file.read()
                    filename = file.filename
                    file_size = len(file_content)
                    unique_id = str(uuid.uuid4())[:8]
                    
                    log_step("UPLOAD_PHOTOS", f"Processando arquivo {i+1}: {filename} ({file_size} bytes)")
                    
                    # Verificar tamanho do arquivo (limite de 10MB para Cloudinary)
                    if file_size > 10 * 1024 * 1024:
                        raise Exception(f"Arquivo muito grande: {file_size} bytes (limite: 10MB)")
                    
                    # Processar a imagem para obter metadados
                    try:
                        image = Image.open(io.BytesIO(file_content))
                        width, height = image.size
                        image_format = image.format
                        log_step("UPLOAD_PHOTOS", f"Imagem processada: {width}x{height}, formato: {image_format}")
                    
                    except Exception as img_error:
                        log_step("UPLOAD_PHOTOS", f"⚠️ Aviso: Erro ao processar imagem: {img_error}")
                        width, height, image_format = 0, 0, 'Desconhecido'
                        
                    # Fazer upload para o Cloudinary
                    log_step("UPLOAD_PHOTOS", f"Iniciando upload para Cloudinary: {filename}")
                    image_url = upload_to_cloudinary(file_content, filename)
                    
                    # Preparar dados para a planilha
                    row_data = [
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        title,
                        description,
                        latitude or '',
                        longitude or '',
                        accuracy or '',
                        filename,
                        file_size,
                        file.content_type,
                        image_url,
                        unique_id,
                        width,
                        height,
                        image_format
                    ]
                    
                    # Adicionar à planilha
                    worksheet.append_row(row_data)
                    
                    results.append({
                        'filename': filename,
                        'size': file_size,
                        'type': file.content_type,
                        'url': image_url,
                        'id': unique_id,
                        'dimensions': f"{width}x{height}",
                        'status': 'success'
                    })
                    
                    successful_uploads += 1
                    log_step("UPLOAD_PHOTOS", f"✅ Arquivo {i+1}/{file_count} processado: {filename} -> {image_url}")
                    
                except Exception as file_error:
                    failed_uploads += 1
                    error_msg = f"Erro ao processar {filename}: {str(file_error)}"
                    log_step("UPLOAD_PHOTOS", error_msg, False)
                    results.append({
                        'filename': filename,
                        'status': 'error',
                        'error': str(file_error)
                    })
        
        return jsonify({
            'success': True,
            'message': f'{file_count} arquivo(s) processado(s)!',
            'results': results,
            'summary': {
                'total_files': file_count,
                'successful': successful_uploads,
                'failed': failed_uploads,
                'worksheet': worksheet_name
            },
            'spreadsheet_title': spreadsheet.title
        })
        
    except Exception as e:
        error_msg = f"❌ Erro no upload de fotos: {str(e)}"
        log_step("UPLOAD_PHOTOS", error_msg, False)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

"""
# ================================
# CONFIGURAÇÃO E INICIALIZAÇÃO
# ================================

if __name__ == '__main__':
    # Inicialização automática ao iniciar o servidor
    log_step("APP_STARTUP", "🚀 Iniciando Sheets App API...")
    
    # Verificar ambiente
    env_check = check_environment_variables()
    
    if env_check['all_found']:
        log_step("APP_STARTUP", "✅ Todas as variáveis de ambiente encontradas")
        
        # Testar conexão em background
        try:
            test_result = test_google_sheets_connection()
            if test_result['success']:
                log_step("APP_STARTUP", "🎉 Conexão com Google Sheets estabelecida com sucesso!")
            else:
                log_step("APP_STARTUP", f"⚠️ Conexão falhou: {test_result.get('error', 'Erro desconhecido')}", False)
        except Exception as e:
            log_step("APP_STARTUP", f"⚠️ Erro durante inicialização: {str(e)}", False)
    else:
        log_step("APP_STARTUP", f"❌ Variáveis ausentes: {env_check['missing_vars']}", False)
    
    # Iniciar servidor
    port = int(os.environ.get('PORT', 5000))
    log_step("APP_STARTUP", f"🌐 Servidor iniciado na porta {port}")
    
    app.run(host='0.0.0.0', port=port, debug=False)