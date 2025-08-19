import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Configuração de logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log'),
        logging.StreamHandler()
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
    'error_messages': []
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
    log_step("ENV_CHECK", "Iniciando verificação de variáveis de ambiente")
    
    required_vars = [
        'GOOGLE_SHEETS_CREDENTIALS',
        'SPREADSHEET_ID'
    ]
    
    missing_vars = []
    found_vars = []
    
    for var in required_vars:
        if os.getenv(var):
            found_vars.append(var)
            # Log apenas os primeiros 50 caracteres por segurança
            var_preview = str(os.getenv(var))[:50] + "..." if len(str(os.getenv(var))) > 50 else str(os.getenv(var))
            log_step("ENV_CHECK", f"✅ {var} encontrada: {var_preview}")
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
    log_step("CREDENTIALS_PARSE", "Iniciando parse das credenciais")
    
    try:
        creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
        if not creds_json:
            raise Exception("Variável GOOGLE_SHEETS_CREDENTIALS não encontrada")
        
        # Tenta fazer parse do JSON
        creds_dict = json.loads(creds_json)
        
        # Verifica campos obrigatórios
        required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
        missing_fields = []
        
        for field in required_fields:
            if field not in creds_dict:
                missing_fields.append(field)
        
        if missing_fields:
            raise Exception(f"Campos obrigatórios ausentes: {missing_fields}")
        
        log_step("CREDENTIALS_PARSE", f"✅ Credenciais válidas. Projeto: {creds_dict.get('project_id')}")
        sheets_status['credentials_found'] = True
        
        return {
            'success': True,
            'project_id': creds_dict.get('project_id'),
            'client_email': creds_dict.get('client_email'),
            'credentials': creds_dict
        }
        
    except json.JSONDecodeError as e:
        error_msg = f"Erro ao fazer parse do JSON: {str(e)}"
        log_step("CREDENTIALS_PARSE", error_msg, False)
        return {'success': False, 'error': error_msg}
    
    except Exception as e:
        error_msg = f"Erro nas credenciais: {str(e)}"
        log_step("CREDENTIALS_PARSE", error_msg, False)
        return {'success': False, 'error': error_msg}

def test_google_sheets_connection():
    """Testa a conexão com o Google Sheets"""
    log_step("SHEETS_CONNECTION", "Iniciando teste de conexão com Google Sheets")
    
    try:
        # Parse das credenciais
        creds_result = parse_credentials()
        if not creds_result['success']:
            return creds_result
        
        # Configuração do escopo
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        log_step("SHEETS_CONNECTION", f"Escopo configurado: {scope}")
        
        # Autenticação
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            creds_result['credentials'], 
            scope
        )
        
        log_step("SHEETS_CONNECTION", "✅ Credenciais de serviço criadas")
        
        # Cliente gspread
        client = gspread.authorize(credentials)
        log_step("SHEETS_CONNECTION", "✅ Cliente gspread autorizado")
        sheets_status['authentication_ok'] = True
        
        # Testa acesso à planilha
        spreadsheet_id = os.getenv('SPREADSHEET_ID')
        if not spreadsheet_id:
            raise Exception("SPREADSHEET_ID não encontrada")
        
        log_step("SHEETS_CONNECTION", f"Tentando acessar planilha: {spreadsheet_id}")
        
        spreadsheet = client.open_by_key(spreadsheet_id)
        log_step("SHEETS_CONNECTION", f"✅ Planilha acessada: {spreadsheet.title}")
        
        # Lista as abas
        worksheets = spreadsheet.worksheets()
        worksheet_names = [ws.title for ws in worksheets]
        log_step("SHEETS_CONNECTION", f"Abas encontradas: {worksheet_names}")
        
        sheets_status['spreadsheet_accessible'] = True
        sheets_status['initialized'] = True
        
        return {
            'success': True,
            'spreadsheet_title': spreadsheet.title,
            'worksheet_names': worksheet_names,
            'client_email': creds_result['client_email'],
            'project_id': creds_result['project_id']
        }
        
    except gspread.exceptions.APIError as e:
        error_msg = f"Erro da API do Google: {str(e)}"
        log_step("SHEETS_CONNECTION", error_msg, False)
        return {'success': False, 'error': error_msg}
    
    except Exception as e:
        error_msg = f"Erro de conexão: {str(e)}"
        log_step("SHEETS_CONNECTION", error_msg, False)
        return {'success': False, 'error': error_msg}

# ================================
# ROTAS DE DEBUG
# ================================

@app.route('/debug/environment', methods=['GET'])
def debug_environment():
    """Endpoint para verificar variáveis de ambiente"""
    log_step("DEBUG_ENV", "Requisição de debug de ambiente recebida")
    
    env_check = check_environment_variables()
    
    # Informações adicionais do ambiente
    python_version = os.sys.version
    environment_info = {
        'python_version': python_version,
        'current_time': datetime.now().isoformat(),
        'environment_variables': env_check,
        'render_info': {
            'service_name': os.getenv('RENDER_SERVICE_NAME', 'Não definido'),
            'git_commit': os.getenv('RENDER_GIT_COMMIT', 'Não definido'),
            'instance_id': os.getenv('RENDER_INSTANCE_ID', 'Não definido'),
        }
    }
    
    return jsonify(environment_info)

@app.route('/debug/credentials', methods=['GET'])
def debug_credentials():
    """Endpoint para testar parse das credenciais"""
    log_step("DEBUG_CREDS", "Requisição de debug de credenciais recebida")
    
    creds_result = parse_credentials()
    
    if creds_result['success']:
        # Remove informações sensíveis da resposta
        safe_result = {
            'success': True,
            'project_id': creds_result.get('project_id'),
            'client_email': creds_result.get('client_email'),
        }
    else:
        safe_result = {
            'success': False,
            'error': creds_result['error']
        }
    
    return jsonify(safe_result)

@app.route('/debug/sheets', methods=['GET'])
def debug_sheets():
    """Endpoint para testar conexão completa com Google Sheets"""
    log_step("DEBUG_SHEETS", "Requisição de debug do Google Sheets recebida")
    
    result = test_google_sheets_connection()
    return jsonify(result)

@app.route('/debug/full', methods=['GET'])
def debug_full():
    """Endpoint para fazer verificação completa passo a passo"""
    log_step("DEBUG_FULL", "Iniciando verificação completa")
    
    # Reset do status
    global sheets_status
    sheets_status = {
        'initialized': False,
        'credentials_found': False,
        'authentication_ok': False,
        'spreadsheet_accessible': False,
        'error_messages': []
    }
    
    # Passo 1: Variáveis de ambiente
    env_result = check_environment_variables()
    
    # Passo 2: Parse das credenciais
    creds_result = parse_credentials()
    
    # Passo 3: Conexão com Google Sheets
    sheets_result = test_google_sheets_connection()
    
    # Resultado completo
    full_result = {
        'timestamp': datetime.now().isoformat(),
        'steps': {
            '1_environment': env_result,
            '2_credentials': creds_result,
            '3_sheets_connection': sheets_result
        },
        'overall_status': sheets_status,
        'success': sheets_result.get('success', False) if isinstance(sheets_result, dict) else False
    }
    
    log_step("DEBUG_FULL", f"Verificação completa finalizada. Sucesso: {full_result['success']}")
    
    return jsonify(full_result)

@app.route('/debug/logs', methods=['GET'])
def get_logs():
    """Endpoint para visualizar logs"""
    try:
        if os.path.exists('debug.log'):
            with open('debug.log', 'r', encoding='utf-8') as f:
                logs = f.readlines()
            
            # Pega as últimas 100 linhas
            recent_logs = logs[-100:] if len(logs) > 100 else logs
            
            return jsonify({
                'logs': recent_logs,
                'total_lines': len(logs),
                'showing_lines': len(recent_logs)
            })
        else:
            return jsonify({'logs': [], 'message': 'Arquivo de log não encontrado'})
    
    except Exception as e:
        return jsonify({'error': f'Erro ao ler logs: {str(e)}'})

# ================================
# ROTAS PRINCIPAIS
# ================================

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint de saúde do servidor"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'sheets_initialized': sheets_status['initialized']
    })

@app.route('/upload', methods=['POST'])
def upload_data():
    """Endpoint principal para upload de dados"""
    log_step("UPLOAD", "Requisição de upload recebida")
    
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
                'message': 'Dados não recebidos'
            }), 400
        
        # Log dos dados recebidos (sem a foto por ser muito grande)
        data_summary = {
            'coords': data.get('coords'),
            'metadata': data.get('metadata'),
            'photo_size': len(data.get('photo', '')) if data.get('photo') else 0
        }
        log_step("UPLOAD", f"Dados recebidos: {data_summary}")
        
        # Aqui você implementaria a lógica de salvar no Google Sheets
        # Por enquanto, apenas retorna sucesso
        
        return jsonify({
            'success': True,
            'message': 'Dados recebidos com sucesso!',
            'id': f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        })
        
    except Exception as e:
        error_msg = f"Erro no upload: {str(e)}"
        log_step("UPLOAD", error_msg, False)
        
        return jsonify({
            'success': False,
            'message': 'Erro interno do servidor',
            'error': error_msg
        }), 500

if __name__ == '__main__':
    log_step("STARTUP", "Iniciando servidor Flask")
    
    # Teste inicial do Google Sheets na inicialização
    log_step("STARTUP", "Testando conexão inicial com Google Sheets")
    initial_test = test_google_sheets_connection()
    
    if initial_test.get('success', False):
        log_step("STARTUP", "✅ Google Sheets inicializado com sucesso")
    else:
        log_step("STARTUP", f"❌ Falha na inicialização do Google Sheets: {initial_test.get('error', 'Erro desconhecido')}", False)
    
    # Inicia o servidor
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)