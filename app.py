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
CORS(app)

# Variáveis globais para status
sheets_status = {
    'initialized': False,
    'credentials_found': False,
    'authentication_ok': False,
    'spreadsheet_accessible': False,
    'error_messages': [],
    'last_test_time': None
}

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

def check_environment_variables():
    """Verifica se as variáveis de ambiente estão definidas"""
    log_step("ENV_CHECK", "🔍 Verificando variáveis de ambiente...")
    
    required_vars = [
        'GOOGLE_SHEETS_CREDENTIALS',
        'SPREADSHEET_ID'
    ]
    
    missing_vars = []
    found_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            found_vars.append(var)
            # Log apenas os primeiros 50 caracteres por segurança
            if len(str(value)) > 50:
                preview = str(value)[:50] + "..."
            else:
                preview = str(value)
            log_step("ENV_CHECK", f"✅ {var} encontrada: {preview}")
        else:
            missing_vars.append(var)
            log_step("ENV_CHECK", f"❌ {var} NÃO ENCONTRADA", False)
    
    # Informações do ambiente Render
    render_info = {
        'service_name': os.getenv('RENDER_SERVICE_NAME', 'Não definido'),
        'git_commit': os.getenv('RENDER_GIT_COMMIT', 'Não definido'),
        'instance_id': os.getenv('RENDER_INSTANCE_ID', 'Não definido'),
    }
    
    log_step("ENV_CHECK", f"Informações do Render: {render_info}")
    
    return {
        'found_vars': found_vars,
        'missing_vars': missing_vars,
        'all_found': len(missing_vars) == 0,
        'render_info': render_info
    }

def parse_credentials():
    """Tenta fazer parse das credenciais JSON"""
    log_step("CREDENTIALS_PARSE", "🔐 Fazendo parse das credenciais...")
    
    try:
        creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
        if not creds_json:
            raise Exception("Variável GOOGLE_SHEETS_CREDENTIALS não encontrada")
        
        # Remove possíveis espaços ou quebras de linha
        creds_json = creds_json.strip()
        
        # Tenta decodificar se estiver em base64 (algumas vezes é armazenado assim)
        try:
            if creds_json.startswith('eyJ'):  # Base64 geralmente começa assim para JSON
                creds_json = base64.b64decode(creds_json).decode('utf-8')
                log_step("CREDENTIALS_PARSE", "Credenciais decodificadas de base64")
        except:
            pass  # Se não for base64, continua com o valor original
        
        # Tenta fazer parse do JSON
        creds_dict = json.loads(creds_json)
        
        # Verifica campos obrigatórios do Google Service Account
        required_fields = [
            'type', 
            'project_id', 
            'private_key_id', 
            'private_key', 
            'client_email',
            'client_id',
            'auth_uri',
            'token_uri'
        ]
        
        missing_fields = []
        for field in required_fields:
            if field not in creds_dict:
                missing_fields.append(field)
        
        if missing_fields:
            raise Exception(f"Campos obrigatórios ausentes no JSON: {missing_fields}")
        
        # Verifica se é realmente um service account
        if creds_dict.get('type') != 'service_account':
            raise Exception(f"Tipo de credencial inválido: {creds_dict.get('type')}. Esperado: service_account")
        
        log_step("CREDENTIALS_PARSE", f"✅ Credenciais válidas! Projeto: {creds_dict.get('project_id')}")
        log_step("CREDENTIALS_PARSE", f"✅ Email do service account: {creds_dict.get('client_email')}")
        
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
        # Parse das credenciais
        creds_result = parse_credentials()
        if not creds_result['success']:
            return creds_result
        
        # Configuração do escopo (atualizado para Google Sheets API v4)
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
        
        log_step("SHEETS_CONNECTION", f"🔑 Escopo configurado: {scopes}")
        
        # Criar credenciais usando google-auth (biblioteca atual)
        credentials = Credentials.from_service_account_info(
            creds_result['credentials'], 
            scopes=scopes
        )
        
        log_step("SHEETS_CONNECTION", "✅ Credenciais Google criadas com sucesso")
        
        # Autorizar cliente gspread
        client = gspread.authorize(credentials)
        log_step("SHEETS_CONNECTION", "✅ Cliente gspread autorizado")
        sheets_status['authentication_ok'] = True
        
        # Testar acesso à planilha
        spreadsheet_id = os.getenv('SPREADSHEET_ID')
        if not spreadsheet_id:
            raise Exception("❌ Variável SPREADSHEET_ID não encontrada")
        
        log_step("SHEETS_CONNECTION", f"📋 Tentando acessar planilha: {spreadsheet_id}")
        
        # Abrir a planilha
        try:
            spreadsheet = client.open_by_key(spreadsheet_id)
            log_step("SHEETS_CONNECTION", f"✅ Planilha acessada: '{spreadsheet.title}'")
        except gspread.exceptions.SpreadsheetNotFound:
            raise Exception(f"❌ Planilha não encontrada. Verifique se o ID está correto e se foi compartilhada com: {creds_result['client_email']}")
        except gspread.exceptions.APIError as api_error:
            raise Exception(f"❌ Erro da API Google: {api_error}")
        
        # Listar abas da planilha
        try:
            worksheets = spreadsheet.worksheets()
            worksheet_names = [ws.title for ws in worksheets]
            log_step("SHEETS_CONNECTION", f"📄 Abas encontradas: {worksheet_names}")
            
            # Testar leitura da primeira aba
            if worksheets:
                first_sheet = worksheets[0]
                try:
                    # Lê apenas as primeiras 5 linhas para teste
                    sample_data = first_sheet.get('A1:E5')
                    log_step("SHEETS_CONNECTION", f"✅ Teste de leitura OK. Dados encontrados: {len(sample_data)} linhas")
                except Exception as read_error:
                    log_step("SHEETS_CONNECTION", f"⚠️ Aviso: Erro ao ler dados de teste: {read_error}")
            
        except Exception as ws_error:
            log_step("SHEETS_CONNECTION", f"⚠️ Aviso: Erro ao listar abas: {ws_error}")
            worksheet_names = ["Erro ao listar abas"]
        
        sheets_status['spreadsheet_accessible'] = True
        sheets_status['initialized'] = True
        sheets_status['last_test_time'] = datetime.now().isoformat()
        
        return {
            'success': True,
            'spreadsheet_id': spreadsheet_id,
            'spreadsheet_title': spreadsheet.title,
            'worksheet_names': worksheet_names,
            'client_email': creds_result['client_email'],
            'project_id': creds_result['project_id'],
            'scopes': scopes,
            'test_time': sheets_status['last_test_time']
        }
        
    except GoogleAuthError as auth_error:
        error_msg = f"❌ Erro de autenticação Google: {str(auth_error)}"
        log_step("SHEETS_CONNECTION", error_msg, False)
        return {'success': False, 'error': error_msg, 'type': 'google_auth_error'}
    
    except gspread.exceptions.APIError as api_error:
        error_msg = f"❌ Erro da API do Google Sheets: {str(api_error)}"
        log_step("SHEETS_CONNECTION", error_msg, False)
        return {'success': False, 'error': error_msg, 'type': 'api_error'}
    
    except Exception as e:
        error_msg = f"❌ Erro geral de conexão: {str(e)}"
        log_step("SHEETS_CONNECTION", error_msg, False)
        return {'success': False, 'error': error_msg, 'type': 'connection_error'}

# ================================
# ROTAS DE DEBUG
# ================================

@app.route('/debug/environment', methods=['GET'])
def debug_environment():
    """🔧 Endpoint para verificar variáveis de ambiente"""
    log_step("DEBUG_ENV", "Requisição de debug de ambiente recebida")
    
    env_check = check_environment_variables()
    
    # Informações adicionais do sistema
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
    
    # Remove informações sensíveis da resposta
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
        
        # Adiciona sugestões baseadas no tipo de erro
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
    
    # Reset do status
    global sheets_status
    sheets_status = {
        'initialized': False,
        'credentials_found': False,
        'authentication_ok': False,
        'spreadsheet_accessible': False,
        'error_messages': [],
        'last_test_time': None
    }
    
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
    
    # Determina o status geral
    overall_success = (
        env_result['all_found'] and 
        creds_result['success'] and 
        sheets_result.get('success', False)
    )
    
    # Resultado completo
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
            'ready_for_uploads': overall_success
        }
    }
    
    # Log do resultado final
    if overall_success:
        log_step("DEBUG_FULL", f"🎉 Verificação completa SUCESSO em {duration:.2f}s")
    else:
        log_step("DEBUG_FULL", f"❌ Verificação completa FALHOU em {duration:.2f}s", False)
    
    return jsonify(full_result)

@app.route('/debug/test-write', methods=['GET'])
def debug_test_write():
    """✍️ Testa escrita na planilha (apenas uma célula)"""
    log_step("DEBUG_WRITE", "Testando escrita na planilha...")
    
    try:
        # Verifica se está inicializado
        if not sheets_status['initialized']:
            sheets_result = test_google_sheets_connection()
            if not sheets_result.get('success', False):
                return jsonify(sheets_result)
        
        # Conecta novamente
        creds_result = parse_credentials()
        if not creds_result['success']:
            return jsonify(creds_result)
        
        credentials = Credentials.from_service_account_info(
            creds_result['credentials'], 
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        
        client = gspread.authorize(credentials)
        spreadsheet = client.open_by_key(os.getenv('SPREADSHEET_ID'))
        worksheet = spreadsheet.sheet1  # Primeira aba
        
        # Escreve dados de teste
        test_data = [
            f"Teste de escrita: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "Dados de teste",
            "Status: OK"
        ]
        
        # Encontra a primeira linha vazia
        values = worksheet.get_all_values()
        next_row = len(values) + 1
        
        # Escreve na próxima linha vazia
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
        return jsonify({
            'success': False,
            'error': error_msg
        })

# ================================
# ROTAS PRINCIPAIS
# ================================

@app.route('/health', methods=['GET'])
def health_check():
    """💓 Endpoint de saúde do servidor"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'sheets_initialized': sheets_status['initialized'],
        'service': 'Google Sheets Debug Server',
        'version': '2.0'
    })

@app.route('/upload', methods=['POST', 'OPTIONS'])
def upload_data():
    """📤 Endpoint principal para upload de dados"""
    
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'})
    
    log_step("UPLOAD", "📨 Requisição de upload recebida")
    
    try:
        # Verifica se o Google Sheets está inicializado
        if not sheets_status['initialized']:
            log_step("UPLOAD", "Google Sheets não inicializado, testando conexão...")
            sheets_result = test_google_sheets_connection()
            
            if not sheets_result.get('success', False):
                return jsonify({
                    'success': False,
                    'message': 'Erro de autenticação com o Google Sheets',
                    'error': sheets_result.get('error', 'Erro desconhecido')
                }), 500
        
        # Processa os dados recebidos
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Nenhum dado recebido'
            }), 400
        
        # Log dos dados recebidos (sem a foto completa)
        coords = data.get('coords', {})
        metadata = data.get('metadata', {})
        photo_size = len(data.get('photo', '')) if data.get('photo') else 0
        
        log_step("UPLOAD", f"Dados: coords={coords}, metadata={metadata}, photo_size={photo_size} bytes")
        
        # Tenta salvar no Google Sheets
        try:
            # Reconecta para garantir
            creds_result = parse_credentials()
            credentials = Credentials.from_service_account_info(
                creds_result['credentials'], 
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            
            client = gspread.authorize(credentials)
            spreadsheet = client.open_by_key(os.getenv('SPREADSHEET_ID'))
            worksheet = spreadsheet.sheet1
            
            # Prepara dados para inserir
            upload_id = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            row_data = [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Timestamp
                upload_id,                                      # ID do upload
                coords.get('latitude', ''),                     # Latitude
                coords.get('longitude', ''),                    # Longitude
                coords.get('accuracy', ''),                     # Precisão GPS
                metadata.get('userAgent', ''),                  # User Agent
                'Foto recebida' if photo_size > 0 else 'Sem foto',  # Status da foto
                photo_size                                      # Tamanho da foto
            ]
            
            # Adiciona na próxima linha vazia
            worksheet.append_row(row_data)
            
            log_step("UPLOAD", f"✅ Dados salvos na planilha com ID: {upload_id}")
            
            return jsonify({
                'success': True,
                'message': 'Dados salvos com sucesso na planilha!',
                'id': upload_id,
                'spreadsheet_title': spreadsheet.title
            })
            
        except Exception as save_error:
            log_step("UPLOAD", f"❌ Erro ao salvar na planilha: {save_error}", False)
            return jsonify({
                'success': False,
                'message': 'Erro ao salvar na planilha',
                'error': str(save_error)
            }), 500
        
    except Exception as e:
        error_msg = f"❌ Erro interno no upload: {str(e)}"
        log_step("UPLOAD", error_msg, False)
        
        return jsonify({
            'success': False,
            'message': 'Erro interno do servidor',
            'error': error_msg
        }), 500

# Adicione estas rotas ao seu app.py existente

@app.route('/api/sheets/data', methods=['GET'])
def get_sheets_data():
    """📊 Endpoint para recuperar dados da planilha"""
    log_step("API_SHEETS_DATA", "📊 Requisição de dados da planilha recebida")
    
    try:
        # Verifica se está inicializado
        if not sheets_status['initialized']:
            sheets_result = test_google_sheets_connection()
            if not sheets_result.get('success', False):
                return jsonify({
                    'success': False,
                    'message': 'Google Sheets não inicializado',
                    'error': sheets_result.get('error', 'Erro desconhecido')
                }), 500
        
        # Parâmetros da requisição
        worksheet_name = request.args.get('worksheet', '')
        limit = request.args.get('limit', type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Conecta ao Google Sheets
        creds_result = parse_credentials()
        if not creds_result['success']:
            return jsonify(creds_result), 500
            
        credentials = Credentials.from_service_account_info(
            creds_result['credentials'], 
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        
        client = gspread.authorize(credentials)
        spreadsheet = client.open_by_key(os.getenv('SPREADSHEET_ID'))
        
        # Seleciona a worksheet
        if worksheet_name:
            try:
                worksheet = spreadsheet.worksheet(worksheet_name)
            except gspread.exceptions.WorksheetNotFound:
                return jsonify({
                    'success': False,
                    'error': f'Aba "{worksheet_name}" não encontrada'
                }), 404
        else:
            worksheet = spreadsheet.sheet1
        
        log_step("API_SHEETS_DATA", f"📋 Acessando aba: {worksheet.title}")
        
        # Recupera todos os dados
        try:
            all_records = worksheet.get_all_records()
            
            # Aplica paginação se necessário
            if limit:
                total_records = len(all_records)
                records = all_records[offset:offset + limit]
            else:
                records = all_records
                total_records = len(records)
            
            log_step("API_SHEETS_DATA", f"✅ {len(records)} registros recuperados")
            
            return jsonify({
                'success': True,
                'data': records,
                'total': total_records,
                'worksheet': worksheet.title,
                'spreadsheet': spreadsheet.title,
                'has_more': limit and (offset + limit) < total_records if limit else False,
                'pagination': {
                    'offset': offset,
                    'limit': limit,
                    'total': total_records
                } if limit else None
            })
            
        except Exception as read_error:
            log_step("API_SHEETS_DATA", f"❌ Erro ao ler dados: {read_error}", False)
            return jsonify({
                'success': False,
                'error': f'Erro ao ler dados da planilha: {str(read_error)}'
            }), 500
        
    except gspread.exceptions.SpreadsheetNotFound:
        return jsonify({
            'success': False,
            'error': 'Planilha não encontrada. Verifique o SPREADSHEET_ID.'
        }), 404
        
    except gspread.exceptions.APIError as api_error:
        return jsonify({
            'success': False,
            'error': f'Erro da API Google: {str(api_error)}'
        }), 500
        
    except Exception as e:
        error_msg = f"❌ Erro interno: {str(e)}"
        log_step("API_SHEETS_DATA", error_msg, False)
        return jsonify({
            'success': False,
            'error': error_msg
        }), 500

@app.route('/api/sheets/worksheets', methods=['GET'])
def get_worksheets():
    """📄 Endpoint para listar todas as abas da planilha"""
    log_step("API_WORKSHEETS", "📄 Requisição de lista de abas recebida")
    
    try:
        # Verifica inicialização
        if not sheets_status['initialized']:
            sheets_result = test_google_sheets_connection()
            if not sheets_result.get('success', False):
                return jsonify({
                    'success': False,
                    'error': 'Google Sheets não inicializado'
                }), 500
        
        # Conecta ao Google Sheets
        creds_result = parse_credentials()
        credentials = Credentials.from_service_account_info(
            creds_result['credentials'], 
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        
        client = gspread.authorize(credentials)
        spreadsheet = client.open_by_key(os.getenv('SPREADSHEET_ID'))
        
        # Lista todas as worksheets
        worksheets = spreadsheet.worksheets()
        
        worksheets_data = []
        for ws in worksheets:
            # Pega informações básicas de cada aba
            try:
                row_count = ws.row_count
                col_count = ws.col_count
                
                # Tenta contar registros com dados (exclui cabeçalho)
                all_values = ws.get_all_values()
                data_rows = len([row for row in all_values if any(cell.strip() for cell in row)]) - 1
                data_rows = max(0, data_rows)  # Não pode ser negativo
                
                worksheets_data.append({
                    'name': ws.title,
                    'id': ws.id,
                    'index': ws.index,
                    'row_count': row_count,
                    'col_count': col_count,
                    'data_rows': data_rows,
                    'url': ws.url
                })
                
            except Exception as ws_error:
                log_step("API_WORKSHEETS", f"⚠️ Erro ao ler aba {ws.title}: {ws_error}")
                worksheets_data.append({
                    'name': ws.title,
                    'id': ws.id,
                    'index': ws.index,
                    'error': str(ws_error)
                })
        
        log_step("API_WORKSHEETS", f"✅ {len(worksheets_data)} abas listadas")
        
        return jsonify({
            'success': True,
            'worksheets': worksheets_data,
            'total': len(worksheets_data),
            'spreadsheet': {
                'title': spreadsheet.title,
                'id': spreadsheet.id,
                'url': spreadsheet.url
            }
        })
        
    except Exception as e:
        error_msg = f"❌ Erro ao listar worksheets: {str(e)}"
        log_step("API_WORKSHEETS", error_msg, False)
        return jsonify({
            'success': False,
            'error': error_msg
        }), 500

@app.route('/api/sheets/stats', methods=['GET'])
def get_sheets_stats():
    """📈 Endpoint para estatísticas gerais da planilha"""
    log_step("API_STATS", "📈 Requisição de estatísticas recebida")
    
    try:
        worksheet_name = request.args.get('worksheet', '')
        
        # Conecta ao Google Sheets
        creds_result = parse_credentials()
        credentials = Credentials.from_service_account_info(
            creds_result['credentials'], 
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        
        client = gspread.authorize(credentials)
        spreadsheet = client.open_by_key(os.getenv('SPREADSHEET_ID'))
        
        if worksheet_name:
            worksheet = spreadsheet.worksheet(worksheet_name)
        else:
            worksheet = spreadsheet.sheet1
        
        # Coleta estatísticas
        all_values = worksheet.get_all_values()
        headers = all_values[0] if all_values else []
        data_rows = all_values[1:] if len(all_values) > 1 else []
        
        # Estatísticas básicas
        stats = {
            'worksheet_name': worksheet.title,
            'total_rows': len(data_rows),
            'total_columns': len(headers),
            'headers': headers,
            'last_updated': datetime.now().isoformat(),
        }
        
        # Estatísticas por coluna
        column_stats = {}
        if data_rows and headers:
            for i, header in enumerate(headers):
                column_data = [row[i] if i < len(row) else '' for row in data_rows]
                non_empty = [cell for cell in column_data if cell.strip()]
                
                column_stats[header] = {
                    'total_values': len(non_empty),
                    'empty_values': len(column_data) - len(non_empty),
                    'unique_values': len(set(non_empty)) if non_empty else 0,
                    'sample_values': non_empty[:5] if non_empty else []
                }
        
        stats['column_stats'] = column_stats
        
        # Estatísticas de uploads (se for uma planilha de uploads)
        if any('timestamp' in header.lower() or 'data' in header.lower() for header in headers):
            upload_stats = analyze_upload_patterns(data_rows, headers)
            stats['upload_patterns'] = upload_stats
        
        log_step("API_STATS", f"✅ Estatísticas geradas para {stats['total_rows']} registros")
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        error_msg = f"❌ Erro ao gerar estatísticas: {str(e)}"
        log_step("API_STATS", error_msg, False)
        return jsonify({
            'success': False,
            'error': error_msg
        }), 500

def analyze_upload_patterns(data_rows, headers):
    """Analisa padrões de upload nos dados"""
    try:
        # Encontra colunas de timestamp
        timestamp_cols = []
        for i, header in enumerate(headers):
            if any(word in header.lower() for word in ['timestamp', 'data', 'hora', 'time']):
                timestamp_cols.append(i)
        
        if not timestamp_cols or not data_rows:
            return {'message': 'Nenhum padrão de timestamp encontrado'}
        
        # Analisa uploads por dia/hora
        uploads_by_day = {}
        uploads_by_hour = {}
        
        for row in data_rows:
            if len(row) > timestamp_cols[0]:
                timestamp_str = row[timestamp_cols[0]]
                try:
                    # Tenta diferentes formatos de data
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S', '%Y-%m-%d']:
                        try:
                            dt = datetime.strptime(timestamp_str, fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        continue  # Não conseguiu fazer parse
                    
                    # Conta por dia
                    day_key = dt.strftime('%Y-%m-%d')
                    uploads_by_day[day_key] = uploads_by_day.get(day_key, 0) + 1
                    
                    # Conta por hora
                    hour_key = dt.hour
                    uploads_by_hour[hour_key] = uploads_by_hour.get(hour_key, 0) + 1
                    
                except Exception:
                    continue
        
        # Encontra dias/horas com mais uploads
        peak_day = max(uploads_by_day.items(), key=lambda x: x[1]) if uploads_by_day else None
        peak_hour = max(uploads_by_hour.items(), key=lambda x: x[1]) if uploads_by_hour else None
        
        return {
            'total_days_with_uploads': len(uploads_by_day),
            'uploads_by_day': dict(sorted(uploads_by_day.items())[-7:]),  # Últimos 7 dias
            'uploads_by_hour': uploads_by_hour,
            'peak_day': {'date': peak_day[0], 'uploads': peak_day[1]} if peak_day else None,
            'peak_hour': {'hour': peak_hour[0], 'uploads': peak_hour[1]} if peak_hour else None,
            'avg_uploads_per_day': sum(uploads_by_day.values()) / len(uploads_by_day) if uploads_by_day else 0
        }
        
    except Exception as e:
        return {'error': f'Erro ao analisar padrões: {str(e)}'}

@app.route('/api/sheets/search', methods=['POST'])
def search_sheets_data():
    """🔍 Endpoint para buscar dados na planilha"""
    log_step("API_SEARCH", "🔍 Requisição de busca recebida")
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Dados de busca não fornecidos'
            }), 400
        
        query = data.get('query', '').strip()
        worksheet_name = data.get('worksheet', '')
        columns = data.get('columns', [])  # Colunas específicas para buscar
        limit = data.get('limit', 100)
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'Query de busca é obrigatória'
            }), 400
        
        # Conecta ao Google Sheets
        creds_result = parse_credentials()
        credentials = Credentials.from_service_account_info(
            creds_result['credentials'], 
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        
        client = gspread.authorize(credentials)
        spreadsheet = client.open_by_key(os.getenv('SPREADSHEET_ID'))
        
        if worksheet_name:
            worksheet = spreadsheet.worksheet(worksheet_name)
        else:
            worksheet = spreadsheet.sheet1
        
        # Recupera dados
        all_records = worksheet.get_all_records()
        
        # Executa busca
        results = []
        query_lower = query.lower()
        
        for record in all_records:
            match_found = False
            
            # Se colunas específicas foram especificadas
            if columns:
                for col in columns:
                    if col in record and query_lower in str(record[col]).lower():
                        match_found = True
                        break
            else:
                # Busca em todas as colunas
                for value in record.values():
                    if query_lower in str(value).lower():
                        match_found = True
                        break
            
            if match_found:
                results.append(record)
                
            # Limite de resultados
            if len(results) >= limit:
                break
        
        log_step("API_SEARCH", f"✅ Busca por '{query}' retornou {len(results)} resultados")
        
        return jsonify({
            'success': True,
            'results': results,
            'total': len(results),
            'query': query,
            'worksheet': worksheet.title,
            'limited': len(results) >= limit
        })
        
    except Exception as e:
        error_msg = f"❌ Erro na busca: {str(e)}"
        log_step("API_SEARCH", error_msg, False)
        return jsonify({
            'success': False,
            'error': error_msg
        }), 500

@app.route('/api/sheets/export', methods=['GET'])
def export_sheets_data():
    """📤 Endpoint para exportar dados da planilha como CSV"""
    log_step("API_EXPORT", "📤 Requisição de export recebida")
    
    try:
        worksheet_name = request.args.get('worksheet', '')
        
        # Conecta ao Google Sheets
        creds_result = parse_credentials()
        credentials = Credentials.from_service_account_info(
            creds_result['credentials'], 
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        
        client = gspread.authorize(credentials)
        spreadsheet = client.open_by_key(os.getenv('SPREADSHEET_ID'))
        
        if worksheet_name:
            worksheet = spreadsheet.worksheet(worksheet_name)
        else:
            worksheet = spreadsheet.sheet1
        
        # Recupera todos os dados
        all_values = worksheet.get_all_values()
        
        if not all_values:
            return jsonify({
                'success': False,
                'error': 'Nenhum dado encontrado para exportar'
            }), 404
        
        # Converte para CSV
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        for row in all_values:
            writer.writerow(row)
        
        csv_content = output.getvalue()
        output.close()
        
        # Prepara resposta
        from flask import make_response
        
        response = make_response(csv_content)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename="{worksheet.title}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        log_step("API_EXPORT", f"✅ Export de {len(all_values)} linhas gerado")
        
        return response
        
    except Exception as e:
        error_msg = f"❌ Erro no export: {str(e)}"
        log_step("API_EXPORT", error_msg, False)
        return jsonify({
            'success': False,
            'error': error_msg
        }), 500


@app.route('/', methods=['GET'])
def index():
    """🏠 Página inicial com informações do serviço"""
    return jsonify({
        'service': 'Google Sheets API Completa',
        'version': '3.0',
        'status': 'running',
        'endpoints': {
            # Endpoints de debug (existentes)
            'health': '/health',
            'debug_full': '/debug/full',
            'debug_environment': '/debug/environment', 
            'debug_credentials': '/debug/credentials',
            'debug_sheets': '/debug/sheets',
            'debug_test_write': '/debug/test-write',
             # Endpoints de API (novos)
            'sheets_data': '/api/sheets/data',
            'worksheets': '/api/sheets/worksheets',
            'sheets_stats': '/api/sheets/stats',
            'search': '/api/sheets/search (POST)',
            'export': '/api/sheets/export',
            
            # Endpoint principal
            'upload': '/upload'
        },
        'sheets_status': sheets_status,
        'api_documentation': {
            'sheets_data': 'GET /api/sheets/data?worksheet=nome&limit=100&offset=0',
            'worksheets': 'GET /api/sheets/worksheets',
            'stats': 'GET /api/sheets/stats?worksheet=nome',
            'search': 'POST /api/sheets/search {"query": "termo", "worksheet": "nome"}',
            'export': 'GET /api/sheets/export?worksheet=nome'
        }
    })

if __name__ == '__main__':
    log_step("STARTUP", "🚀 Iniciando servidor Flask...")
    
    # Teste inicial do Google Sheets
    log_step("STARTUP", "🔍 Executando teste inicial...")
    initial_test = test_google_sheets_connection()
    
    if initial_test.get('success', False):
        log_step("STARTUP", "✅ Google Sheets inicializado com sucesso!")
    else:
        log_step("STARTUP", f"⚠️ Aviso: Falha na inicialização - {initial_test.get('error', 'Erro desconhecido')}", False)
        log_step("STARTUP", "ℹ️ Servidor iniciará mesmo assim. Use /debug/full para diagnosticar.")
    
    # Inicia o servidor
    port = int(os.environ.get('PORT', 5000))
    log_step("STARTUP", f"🌐 Servidor rodando na porta {port}")
    
    app.run(debug=False, host='0.0.0.0', port=port)