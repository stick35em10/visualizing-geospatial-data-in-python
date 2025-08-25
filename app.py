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


def upload_to_drive(file_content, filename, mime_type):
    """Faz upload de um arquivo para o Google Drive e retorna a URL pública"""
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseUpload
        
        # Obter credenciais
        creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
        if not creds_json:
            raise Exception("Variável GOOGLE_SHEETS_CREDENTIALS não encontrada")
        
        creds_json = creds_json.strip()
        if creds_json.startswith('eyJ'):
            creds_json = base64.b64decode(creds_json).decode('utf-8')
        
        creds_dict = json.loads(creds_json)
        credentials = Credentials.from_service_account_info(creds_dict)
        
        # Criar serviço do Drive
        drive_service = build('drive', 'v3', credentials=credentials)
        
        # Sanitizar o nome do arquivo - remover caracteres problemáticos
        import re
        safe_filename = re.sub(r'[^\w\.-]', '_', filename)
        
        # Criar arquivo no Drive
        file_metadata = {
            'name': safe_filename, # Usar nome sanitizado
            'parents': ['root'],  # Você pode especificar uma pasta específica
            'mimeType': mime_type
        }
        
        media = MediaIoBaseUpload(io.BytesIO(file_content), 
                                mimetype=mime_type,
                                resumable=True)
        
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink, webContentLink'
        ).execute()
        
        # Tornar o arquivo público
        drive_service.permissions().create(
            fileId=file['id'],
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()
        
        # Obter link público
        file_url = f"https://drive.google.com/uc?id={file['id']}"
        
        log_step("DRIVE_UPLOAD", f"✅ Arquivo {filename} upload para Drive: {file_url}")
        return file_url
        
    except Exception as e:
        log_step("DRIVE_UPLOAD", f"❌ Erro no upload para Drive: {str(e)}", False)
        raise
    
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

@app.route('/api/upload/photos', methods=['POST', 'OPTIONS'])
def upload_photos():
    """📸 Endpoint completo para upload de fotos com armazenamento no Drive"""
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
                    
                    # grep -n "try" app.py
                    # Processar a imagem para obter metadados
                    try:
                        image = Image.open(io.BytesIO(file_content))
                        width, height = image.size
                        image_format = image.format
                        log_step("UPLOAD_PHOTOS", f"Imagem processada: {width}x{height}, formato: {image_format}")
                    
                    except Exception as img_error:
                        log_step("UPLOAD_PHOTOS", f"⚠️ Aviso: Erro ao processar imagem: {img_error}")
                        width, height, image_format = 0, 0, 'Desconhecido'
                        
                    # Fazer upload para o Google Drive
                    log_step("UPLOAD_PHOTOS", f"Iniciando upload para Drive: {filename}")
                    drive_url = upload_to_drive(file_content, f"{unique_id}_{filename}", file.content_type)
                    
                    # Preparar dados para a planilha
                    row_data = [
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        title,
                        description,
                        latitude or '',
                        longitude or '',
                        accuracy or '',
                        filename, # Nome original mantido para referência
                        file_size,
                        file.content_type,
                        drive_url,  # URL pública da imagem
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
                        'url': drive_url,
                        'id': unique_id,
                        'dimensions': f"{width}x{height}",
                        'status': 'success'
                    })
                    
                    log_step("UPLOAD_PHOTOS", f"✅ Arquivo {i+1}/{file_count} processado: {filename} -> {drive_url}")
                    
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

@app.route('/api/sheets/worksheets', methods=['GET'])
def get_worksheets():
    """📄 Lista todas as abas/worksheets da planilha"""
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

"""
@app.route('/api/upload/photos', methods=['POST', 'OPTIONS'])
def upload_photos():
    📸 Endpoint para upload de fotos com metadados
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
        
        log_step("UPLOAD_PHOTOS", f"Processando {file_count} arquivo(s) para a aba '{worksheet_name}'")
        
        client, spreadsheet = get_sheets_client()
        
        # Verificar se a worksheet existe, se não, criar
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows="100", cols="10")
            # Adicionar cabeçalhos
            headers = ["Data", "Título", "Descrição", "Latitude", "Longitude", "Precisão", "Nome do Arquivo", "Tamanho", "Tipo"]
            worksheet.append_row(headers)
            log_step("UPLOAD_PHOTOS", f"✅ Nova worksheet criada: {worksheet_name}")
        
        # Processar cada arquivo
        results = []
        for i, file in enumerate(uploaded_files):
            if file and file.filename:
                filename = file.filename
                file_size = len(file.read())
                file.seek(0)  # Reset file pointer
                
                # Aqui você pode salvar o arquivo se necessário, ou apenas registrar os metadados
                # Por enquanto, vamos apenas registrar os metadados na planilha
                
                row_data = [
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    title,
                    description,
                    latitude or '',
                    longitude or '',
                    accuracy or '',
                    filename,
                    file_size,
                    file.content_type
                ]
                
                worksheet.append_row(row_data)
                results.append({
                    'filename': filename,
                    'size': file_size,
                    'type': file.content_type,
                    'status': 'success'
                })
                
                log_step("UPLOAD_PHOTOS", f"✅ Arquivo {i+1}/{file_count} processado: {filename}")
        
        return jsonify({
            'success': True,
            'message': f'{file_count} arquivo(s) processado(s) com sucesso!',
            'results': results,
            'worksheet': worksheet_name,
            'spreadsheet_title': spreadsheet.title
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

@app.route('/api/sheets/data', methods=['GET'])
def get_sheet_data():
    """📊 Retorna os dados de uma worksheet específica"""
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
    """ℹ️ Retorna informações gerais sobre a planilha"""
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
    """🔧 Endpoint para verificar variáveis de ambiente"""
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
    """🔐 Endpoint para testar parse das credenciais"""
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
    """📊 Endpoint para testar conexão completa com Google Sheets"""
    log_step("DEBUG_SHEETS", "Requisição de debug do Google Sheets recebida")
    result = test_google_sheets_connection()
    return jsonify(result)

@app.route('/debug/full', methods=['GET'])
def debug_full():
    """🔍 Endpoint para verificação completa passo a passo"""
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
    """✍️ Testa escrita na planilha"""
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
            'data': test_data,
            'spreadsheet_title': spreadsheet.title
        })
        
    except Exception as e:
        error_msg = f"❌ Erro ao testar escrita: {str(e)}"
        log_step("DEBUG_WRITE", error_msg, False)
        return jsonify({'success': False, 'error': error_msg})

# ================================
# ROTAS PRINCIPAIS ORIGINAIS
# ================================

@app.route('/health', methods=['GET'])
def health_check():
    """💓 Endpoint de saúde do servidor"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'sheets_initialized': sheets_status['initialized'],
        'service': 'Google Sheets API Server',
        'version': '3.0',
        'available_endpoints': {
            'api': ['/api/sheets/data', '/api/sheets/worksheets', '/api/sheets/info'],
            'debug': ['/debug/full', '/debug/sheets', '/debug/credentials', '/debug/environment'],
            'main': ['/health', '/upload', '/']
        }
    })

@app.route('/upload', methods=['POST', 'OPTIONS'])
def upload_data():
    """📤 Endpoint principal para upload de dados"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'})
    
    log_step("UPLOAD", "📨 Requisição de upload recebida")
    
    try:
        if not sheets_status['initialized']:
            sheets_result = test_google_sheets_connection()
            if not sheets_result.get('success', False):
                return jsonify({
                    'success': False,
                    'message': 'Erro de autenticação com o Google Sheets',
                    'error': sheets_result.get('error', 'Erro desconhecido')
                }), 500
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Nenhum dado recebido'}), 400
        
        coords = data.get('coords', {})
        metadata = data.get('metadata', {})
        photo_size = len(data.get('photo', '')) if data.get('photo') else 0
        
        log_step("UPLOAD", f"Processando upload: coords={coords}, metadata={metadata}, photo_size={photo_size}")
        
        try:
            client, spreadsheet = get_sheets_client()
            worksheet = spreadsheet.sheet1
            
            upload_id = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            row_data = [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                upload_id,
                coords.get('latitude', ''),
                coords.get('longitude', ''),
                coords.get('accuracy', ''),
                metadata.get('userAgent', ''),
                'Foto recebida' if photo_size > 0 else 'Sem foto',
                photo_size
            ]
            
            worksheet.append_row(row_data)
            log_step("UPLOAD", f"✅ Dados salvos com ID: {upload_id}")
            
            return jsonify({
                'success': True,
                'message': 'Dados salvos com sucesso!',
                'id': upload_id,
                'spreadsheet_title': spreadsheet.title
            })
            
        except Exception as save_error:
            log_step("UPLOAD", f"❌ Erro ao salvar: {save_error}", False)
            return jsonify({
                'success': False,
                'message': 'Erro ao salvar na planilha',
                'error': str(save_error)
            }), 500
        
    except Exception as e:
        error_msg = f"❌ Erro interno: {str(e)}"
        log_step("UPLOAD", error_msg, False)
        return jsonify({
            'success': False,
            'message': 'Erro interno do servidor',
            'error': error_msg
        }), 500

@app.route('/', methods=['GET'])
def index():
    """🏠 Página inicial com informações do serviço"""
    return jsonify({
        'service': 'Google Sheets API Server',
        'version': '3.0',
        'status': 'running',
        'endpoints': {
            'api': {
                'sheets_data': '/api/sheets/data?worksheet=<name>',
                'worksheets': '/api/sheets/worksheets',
                'info': '/api/sheets/info'
            },
            'debug': {
                'full': '/debug/full',
                'environment': '/debug/environment', 
                'credentials': '/debug/credentials',
                'sheets': '/debug/sheets',
                'test_write': '/debug/test-write'
            },
            'main': {
                'health': '/health',
                'upload': '/upload',
                'index': '/'
            }
        },
        'sheets_status': sheets_status,
        'client_html_compatible': True
    })

if __name__ == '__main__':
    log_step("STARTUP", "🚀 Iniciando Google Sheets API Server v3.0...")
    
    # Teste inicial
    log_step("STARTUP", "🔍 Executando teste inicial...")
    initial_test = test_google_sheets_connection()
    
    if initial_test.get('success', False):
        log_step("STARTUP", "✅ Google Sheets inicializado com sucesso!")
    else:
        log_step("STARTUP", f"⚠️ Falha na inicialização - {initial_test.get('error', 'Erro desconhecido')}", False)
    
    port = int(os.environ.get('PORT', 5000))
    log_step("STARTUP", f"🌐 Servidor API rodando na porta {port}")
    
    app.run(debug=False, host='0.0.0.0', port=port)