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

@app.route('/', methods=['GET'])
def index():
    """🏠 Página inicial com informações do serviço"""
    return jsonify({
        'service': 'Google Sheets Debug API',
        'version': '2.0',
        'status': 'running',
        'endpoints': {
            'health': '/health',
            'debug_full': '/debug/full',
            'debug_environment': '/debug/environment', 
            'debug_credentials': '/debug/credentials',
            'debug_sheets': '/debug/sheets',
            'debug_test_write': '/debug/test-write',
            'upload': '/upload'
        },
        'sheets_status': sheets_status
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