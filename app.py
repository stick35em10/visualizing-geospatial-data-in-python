import os
import json
import logging
import base64
import uuid
import io
import re
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials
from google.auth.exceptions import GoogleAuthError
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError

# Imports opcionais para processamento de imagens
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️ PIL não disponível - metadados de imagem limitados")

# Configuração de logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# CORS mais permissivo para desenvolvimento
CORS(app, resources={
    r"/*": {
        "origins": [
            "https://stick35em10.github.io",
            "http://localhost:*",
            "http://127.0.0.1:*",
            "https://*.github.io"
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": True,
        "max_age": 3600
    }
})

# Variáveis globais
sheets_status = {
    'initialized': False,
    'credentials_found': False,
    'authentication_ok': False,
    'spreadsheet_accessible': False,
    'drive_accessible': False,
    'error_messages': [],
    'last_test_time': None
}

_client_cache = None
_spreadsheet_cache = None
_drive_service_cache = None

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

def get_credentials():
    """Retorna as credenciais do Google processadas"""
    try:
        creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
        if not creds_json:
            raise Exception("Variável GOOGLE_SHEETS_CREDENTIALS não encontrada")
        
        creds_json = creds_json.strip()
        
        # Decodificar base64 se necessário
        if creds_json.startswith('eyJ'):
            creds_json = base64.b64decode(creds_json).decode('utf-8')
        
        creds_dict = json.loads(creds_json)
        
        # Validar campos obrigatórios
        required_fields = ['type', 'project_id', 'private_key', 'client_email']
        for field in required_fields:
            if field not in creds_dict:
                raise Exception(f"Campo obrigatório ausente: {field}")
        
        if creds_dict.get('type') != 'service_account':
            raise Exception(f"Tipo de credencial inválido: {creds_dict.get('type')}")
        
        return creds_dict
        
    except Exception as e:
        log_step("CREDENTIALS", f"❌ Erro nas credenciais: {str(e)}", False)
        raise

def get_sheets_client():
    """Retorna cliente do Google Sheets com cache"""
    global _client_cache, _spreadsheet_cache
    
    try:
        if _client_cache is not None and _spreadsheet_cache is not None:
            return _client_cache, _spreadsheet_cache
        
        creds_dict = get_credentials()
        
        # Escopos para Sheets e Drive
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(credentials)
        
        spreadsheet_id = os.getenv('SPREADSHEET_ID')
        if not spreadsheet_id:
            raise Exception("Variável SPREADSHEET_ID não encontrada")
        
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        # Cache dos objetos
        _client_cache = client
        _spreadsheet_cache = spreadsheet
        
        log_step("SHEETS_CLIENT", f"✅ Conectado à planilha: {spreadsheet.title}")
        return client, spreadsheet
        
    except Exception as e:
        log_step("SHEETS_CLIENT", f"❌ Erro ao conectar: {str(e)}", False)
        raise

def get_drive_service():
    """Retorna serviço do Google Drive com cache"""
    global _drive_service_cache
    
    try:
        if _drive_service_cache is not None:
            return _drive_service_cache
        
        creds_dict = get_credentials()
        scopes = ['https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        
        _drive_service_cache = build('drive', 'v3', credentials=credentials)
        
        log_step("DRIVE_SERVICE", "✅ Serviço Google Drive inicializado")
        return _drive_service_cache
        
    except Exception as e:
        log_step("DRIVE_SERVICE", f"❌ Erro ao inicializar Drive: {str(e)}", False)
        raise

def create_shared_folder():
    """Cria uma pasta compartilhada no Google Drive para armazenar as imagens"""
    try:
        drive_service = get_drive_service()
        
        folder_name = f"SheetsApp_Images_{datetime.now().strftime('%Y%m%d')}"
        
        # Verificar se a pasta já existe
        results = drive_service.files().list(
            q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id, name)"
        ).execute()
        
        files = results.get('files', [])
        
        if files:
            folder_id = files[0]['id']
            log_step("DRIVE_FOLDER", f"✅ Pasta existente encontrada: {folder_id}")
        else:
            # Criar nova pasta
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            folder = drive_service.files().create(
                body=folder_metadata,
                fields='id, name'
            ).execute()
            
            folder_id = folder.get('id')
            
            # Tornar a pasta pública
            drive_service.permissions().create(
                fileId=folder_id,
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()
            
            log_step("DRIVE_FOLDER", f"✅ Nova pasta criada: {folder_name} ({folder_id})")
        
        return folder_id
        
    except Exception as e:
        log_step("DRIVE_FOLDER", f"❌ Erro ao criar/encontrar pasta: {str(e)}", False)
        return None

def upload_to_drive(file_content, filename, mime_type):
    """Upload de arquivo para o Google Drive com tratamento robusto"""
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
            fields='id, webViewLink, webContentLink, parents'
        ).execute()
        
        file_id = file.get('id')
        
        # Tornar o arquivo público
        try:
            drive_service.permissions().create(
                fileId=file_id,
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()
            
            # URL direta para visualização
            file_url = f"https://drive.google.com/uc?id={file_id}"
            
            log_step("DRIVE_UPLOAD", f"✅ Upload realizado: {unique_filename} -> {file_url}")
            return file_url, file_id, unique_filename
            
        except Exception as perm_error:
            log_step("DRIVE_UPLOAD", f"⚠️ Aviso: Erro ao tornar público: {perm_error}")
            # Retorna mesmo assim, o arquivo pode estar acessível
            file_url = f"https://drive.google.com/file/d/{file_id}/view"
            return file_url, file_id, unique_filename
            
    except HttpError as e:
        if 'storageQuotaExceeded' in str(e):
            raise Exception("Quota de armazenamento excedida. Configure um Shared Drive ou use OAuth.")
        else:
            raise Exception(f"Erro HTTP do Drive: {e.resp.status} - {str(e)}")
    
    except Exception as e:
        raise Exception(f"Erro no upload: {str(e)}")

def test_google_sheets_connection():
    """Testa conexão completa com Google Sheets e Drive"""
    log_step("CONNECTION_TEST", "🚀 Iniciando teste de conexão...")
    
    try:
        # Teste 1: Credenciais
        creds_dict = get_credentials()
        log_step("CONNECTION_TEST", f"✅ Credenciais válidas - Email: {creds_dict.get('client_email')}")
        sheets_status['credentials_found'] = True
        
        # Teste 2: Google Sheets
        client, spreadsheet = get_sheets_client()
        worksheets = spreadsheet.worksheets()
        worksheet_names = [ws.title for ws in worksheets]
        
        log_step("CONNECTION_TEST", f"✅ Sheets conectado - Abas: {worksheet_names}")
        sheets_status['authentication_ok'] = True
        sheets_status['spreadsheet_accessible'] = True
        
        # Teste 3: Google Drive
        try:
            drive_service = get_drive_service()
            # Teste simples de listagem
            results = drive_service.files().list(pageSize=1, fields="files(id, name)").execute()
            log_step("CONNECTION_TEST", "✅ Drive conectado")
            sheets_status['drive_accessible'] = True
        except Exception as drive_error:
            log_step("CONNECTION_TEST", f"⚠️ Drive com limitações: {drive_error}")
            sheets_status['drive_accessible'] = False
        
        sheets_status['initialized'] = True
        sheets_status['last_test_time'] = datetime.now().isoformat()
        
        return {
            'success': True,
            'spreadsheet_id': os.getenv('SPREADSHEET_ID'),
            'spreadsheet_title': spreadsheet.title,
            'worksheet_names': worksheet_names,
            'drive_accessible': sheets_status['drive_accessible'],
            'client_email': creds_dict.get('client_email'),
            'test_time': sheets_status['last_test_time']
        }
        
    except Exception as e:
        error_msg = f"❌ Erro de conexão: {str(e)}"
        log_step("CONNECTION_TEST", error_msg, False)
        return {'success': False, 'error': error_msg}

# ================================
# ROTAS DE API
# ================================

@app.route('/health', methods=['GET'])
def health_check():
    """💓 Endpoint de saúde do servidor"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'sheets_initialized': sheets_status['initialized'],
        'drive_accessible': sheets_status['drive_accessible'],
        'service': 'Google Sheets & Drive API Server',
        'version': '4.0',
        'features': {
            'sheets_read_write': True,
            'image_upload': sheets_status['drive_accessible'],
            'multiple_worksheets': True
        }
    })

@app.route('/debug/full', methods=['GET'])
def debug_full():
    """🔍 Diagnóstico completo do sistema"""
    log_step("DEBUG_FULL", "🚀 Iniciando diagnóstico completo...")
    
    # Reset status
    global sheets_status, _client_cache, _spreadsheet_cache, _drive_service_cache
    sheets_status = {
        'initialized': False,
        'credentials_found': False,
        'authentication_ok': False,
        'spreadsheet_accessible': False,
        'drive_accessible': False,
        'error_messages': [],
        'last_test_time': None
    }
    _client_cache = None
    _spreadsheet_cache = None
    _drive_service_cache = None
    
    start_time = datetime.now()
    
    # Verificar variáveis de ambiente
    env_vars = ['GOOGLE_SHEETS_CREDENTIALS', 'SPREADSHEET_ID']
    missing_vars = [var for var in env_vars if not os.getenv(var)]
    
    env_check = {
        'required_vars': env_vars,
        'missing_vars': missing_vars,
        'all_found': len(missing_vars) == 0
    }
    
    # Testar conexões
    connection_result = test_google_sheets_connection()
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    overall_success = env_check['all_found'] and connection_result.get('success', False)
    
    return jsonify({
        'timestamp': end_time.isoformat(),
        'duration_seconds': duration,
        'environment': env_check,
        'connections': connection_result,
        'status': sheets_status,
        'success': overall_success,
        'summary': {
            'ready_for_use': overall_success,
            'sheets_ok': sheets_status['spreadsheet_accessible'],
            'drive_ok': sheets_status['drive_accessible'],
            'can_upload_images': sheets_status['drive_accessible']
        }
    })

@app.route('/api/sheets/worksheets', methods=['GET'])
def get_worksheets():
    """📄 Lista abas da planilha"""
    log_step("API_WORKSHEETS", "Listando worksheets...")
    
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
            'spreadsheet_title': spreadsheet.title,
            'total_worksheets': len(worksheet_list)
        })
        
    except Exception as e:
        error_msg = f"Erro ao listar worksheets: {str(e)}"
        log_step("API_WORKSHEETS", error_msg, False)
        return jsonify({'success': False, 'error': error_msg}), 500

@app.route('/api/sheets/data', methods=['GET'])
def get_sheet_data():
    """📊 Obtém dados de uma worksheet"""
    log_step("API_DATA", "Obtendo dados da planilha...")
    
    try:
        worksheet_name = request.args.get('worksheet', '')
        max_rows = request.args.get('max_rows', 'all')
        
        client, spreadsheet = get_sheets_client()
        
        # Selecionar worksheet
        if worksheet_name:
            try:
                worksheet = spreadsheet.worksheet(worksheet_name)
            except gspread.exceptions.WorksheetNotFound:
                return jsonify({
                    'success': False,
                    'error': f'Worksheet "{worksheet_name}" não encontrada'
                }), 404
        else:
            worksheet = spreadsheet.sheet1
        
        log_step("API_DATA", f"Lendo dados de: {worksheet.title}")
        
        # Obter dados
        try:
            all_records = worksheet.get_all_records()
            
            if not all_records:
                all_values = worksheet.get_all_values()
                if all_values and len(all_values) > 1:
                    headers = all_values[0]
                    data_rows = all_values[1:]
                    
                    all_records = []
                    for row in data_rows:
                        record = {}
                        for i, header in enumerate(headers):
                            value = row[i] if i < len(row) else ''
                            record[header] = value
                        all_records.append(record)
            
            # Aplicar limite se especificado
            if max_rows != 'all':
                all_records = all_records[:int(max_rows)]
            
            total_rows = len(all_records)
            total_columns = len(all_records[0].keys()) if all_records else 0
            
            log_step("API_DATA", f"✅ {total_rows} linhas, {total_columns} colunas")
            
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
            return jsonify({
                'success': False,
                'error': f'Erro ao ler dados: {str(data_error)}'
            }), 500
        
    except Exception as e:
        error_msg = f"Erro interno: {str(e)}"
        log_step("API_DATA", error_msg, False)
        return jsonify({'success': False, 'error': error_msg}), 500

@app.route('/api/upload/photos', methods=['POST', 'OPTIONS'])
def upload_photos():
    """📸 Upload de fotos com metadados para Google Drive e Sheets"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    log_step("UPLOAD_PHOTOS", "🖼️ Iniciando upload de fotos...")
    
    try:
        # Verificar inicialização
        if not sheets_status['initialized']:
            connection_result = test_google_sheets_connection()
            if not connection_result.get('success'):
                return jsonify({
                    'success': False,
                    'message': 'Falha na conexão com Google Services',
                    'error': connection_result.get('error')
                }), 500
        
        # Verificar se o Drive está acessível
        if not sheets_status['drive_accessible']:
            return jsonify({
                'success': False,
                'message': 'Google Drive não está acessível. Verifique as permissões.',
                'error': 'Drive permissions required for image upload'
            }), 503
        
        # Obter dados do formulário
        title = request.form.get('title', 'Foto sem título')
        description = request.form.get('description', '')
        worksheet_name = request.form.get('worksheet', 'Imagens')
        latitude = request.form.get('latitude', '')
        longitude = request.form.get('longitude', '')
        accuracy = request.form.get('accuracy', '')
        
        # Processar arquivos
        uploaded_files = request.files.getlist('photos')
        if not uploaded_files or all(not f.filename for f in uploaded_files):
            return jsonify({
                'success': False,
                'message': 'Nenhum arquivo válido enviado'
            }), 400
        
        log_step("UPLOAD_PHOTOS", f"Processando {len(uploaded_files)} arquivo(s)...")
        
        client, spreadsheet = get_sheets_client()
        
        # Verificar/criar worksheet
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows="1000", cols="15")
            headers = [
                "Data", "Título", "Descrição", "Latitude", "Longitude", "Precisão",
                "Nome Original", "Nome no Drive", "Tamanho", "Tipo", "URL da Imagem",
                "ID do Arquivo", "Largura", "Altura", "Formato"
            ]
            worksheet.append_row(headers)
            log_step("UPLOAD_PHOTOS", f"✅ Worksheet criada: {worksheet_name}")
        
        # Processar cada arquivo
        results = []
        successful_uploads = 0
        
        for i, file in enumerate(uploaded_files):
            if not file or not file.filename:
                continue
                
            try:
                file_content = file.read()
                original_filename = file.filename
                file_size = len(file_content)
                unique_id = uuid.uuid4().hex[:8]
                
                log_step("UPLOAD_PHOTOS", f"[{i+1}] Processando: {original_filename} ({file_size} bytes)")
                
                # Validar tamanho (limite de 10MB)
                if file_size > 10 * 1024 * 1024:
                    raise Exception(f"Arquivo muito grande: {file_size/1024/1024:.1f}MB (limite: 10MB)")
                
                # Processar metadados da imagem
                width, height, image_format = 0, 0, 'Desconhecido'
                if PIL_AVAILABLE:
                    try:
                        with Image.open(io.BytesIO(file_content)) as img:
                            width, height = img.size
                            image_format = img.format or 'Desconhecido'
                    except Exception as img_error:
                        log_step("UPLOAD_PHOTOS", f"⚠️ Erro ao processar imagem: {img_error}")
                
                # Upload para Google Drive
                drive_url, file_id, drive_filename = upload_to_drive(
                    file_content, original_filename, file.content_type or 'application/octet-stream'
                )
                
                # Dados para a planilha
                row_data = [
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Data
                    title,                                          # Título
                    description,                                    # Descrição
                    latitude,                                       # Latitude
                    longitude,                                      # Longitude
                    accuracy,                                       # Precisão GPS
                    original_filename,                              # Nome original
                    drive_filename,                                 # Nome no Drive
                    file_size,                                      # Tamanho
                    file.content_type or 'unknown',               # Tipo MIME
                    drive_url,                                      # URL da imagem
                    file_id,                                        # ID do arquivo no Drive
                    width,                                          # Largura
                    height,                                         # Altura
                    image_format                                    # Formato da imagem
                ]
                
                # Adicionar à planilha
                worksheet.append_row(row_data)
                successful_uploads += 1
                
                results.append({
                    'original_filename': original_filename,
                    'drive_filename': drive_filename,
                    'size': file_size,
                    'type': file.content_type,
                    'url': drive_url,
                    'file_id': file_id,
                    'dimensions': f"{width}x{height}" if width > 0 else "N/A",
                    'status': 'success'
                })
                
                log_step("UPLOAD_PHOTOS", f"✅ [{i+1}] Upload concluído: {original_filename}")
                
            except Exception as file_error:
                error_msg = f"Erro em {original_filename}: {str(file_error)}"
                log_step("UPLOAD_PHOTOS", f"❌ [{i+1}] {error_msg}", False)
                
                results.append({
                    'original_filename': original_filename,
                    'status': 'error',
                    'error': str(file_error)
                })
        
        return jsonify({
            'success': True,
            'message': f'{successful_uploads} arquivo(s) enviado(s) com sucesso!',
            'results': results,
            'summary': {
                'total_files': len(uploaded_files),
                'successful': successful_uploads,
                'failed': len(uploaded_files) - successful_uploads,
                'worksheet': worksheet_name,
                'spreadsheet_title': spreadsheet.title
            }
        })
        
    except Exception as e:
        error_msg = f"❌ Erro no upload: {str(e)}"
        log_step("UPLOAD_PHOTOS", error_msg, False)
        return jsonify({
            'success': False,
            'message': 'Erro no processamento do upload',
            'error': str(e)
        }), 500

@app.route('/upload', methods=['POST', 'OPTIONS'])
def upload_data():
    """📤 Upload básico de dados (compatibilidade)"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'})
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Nenhum dado recebido'}), 400
        
        client, spreadsheet = get_sheets_client()
        worksheet = spreadsheet.sheet1
        
        coords = data.get('coords', {})
        metadata = data.get('metadata', {})
        
        upload_id = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        row_data = [
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            upload_id,
            coords.get('latitude', ''),
            coords.get('longitude', ''),
            coords.get('accuracy', ''),
            metadata.get('userAgent', ''),
            len(data.get('photo', '')) if data.get('photo') else 0
        ]
        
        worksheet.append_row(row_data)
        
        return jsonify({
            'success': True,
            'message': 'Dados salvos com sucesso!',
            'id': upload_id,
            'spreadsheet_title': spreadsheet.title
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Erro interno do servidor',
            'error': str(e)
        }), 500

@app.route('/', methods=['GET'])
def index():
    """🏠 Página inicial"""
    return jsonify({
        'service': 'Google Sheets & Drive API Server',
        'version': '4.0',
        'status': 'running',
        'features': {
            'sheets_integration': True,
            'drive_integration': sheets_status.get('drive_accessible', False),
            'image_upload': sheets_status.get('drive_accessible', False),
            'multiple_worksheets': True
        },
        'endpoints': {
            'health': '/health',
            'debug': '/debug/full',
            'worksheets': '/api/sheets/worksheets',
            'data': '/api/sheets/data?worksheet=<name>',
            'upload_photos': '/api/upload/photos',
            'upload_basic': '/upload'
        },
        'status': sheets_status,
        'instructions': [
            "1. Teste a conexão em /debug/full",
            "2. Liste abas em /api/sheets/worksheets",
            "3. Visualize dados em /api/sheets/data?worksheet=<name>",
            "4. Envie fotos em /api/upload/photos"
        ]
    })

if __name__ == '__main__':
    log_step("STARTUP", "🚀 Iniciando servidor v4.0...")
    
    # Teste inicial
    initial_test = test_google_sheets_connection()
    
    if initial_test.get('success'):
        log_step("STARTUP", "✅ Inicialização bem-sucedida!")
    else:
        log_step("STARTUP", f"⚠️ Inicialização com problemas: {initial_test.get('error')}")
    
    port = int(os.environ.get('PORT', 5000))
    log_step("STARTUP", f"🌐 Servidor rodando na porta {port}")
    
    app.run(debug=False, host='0.0.0.0', port=port)
