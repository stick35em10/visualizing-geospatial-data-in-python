import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, send_file, make_response
from flask_cors import CORS
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import io
import csv

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
        
        creds_dict = json.loads(creds_json)
        
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

def get_sheets_client():
    """Retorna cliente autenticado do Google Sheets"""
    try:
        creds_result = parse_credentials()
        if not creds_result['success']:
            return None, creds_result['error']
        
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            creds_result['credentials'], 
            scope
        )
        
        client = gspread.authorize(credentials)
        return client, None
        
    except Exception as e:
        return None, str(e)

def test_google_sheets_connection():
    """Testa a conexão com o Google Sheets"""
    log_step("SHEETS_CONNECTION", "Iniciando teste de conexão com Google Sheets")
    
    try:
        creds_result = parse_credentials()
        if not creds_result['success']:
            return creds_result
        
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        log_step("SHEETS_CONNECTION", f"Escopo configurado: {scope}")
        
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            creds_result['credentials'], 
            scope
        )
        
        log_step("SHEETS_CONNECTION", "✅ Credenciais de serviço criadas")
        
        client = gspread.authorize(credentials)
        log_step("SHEETS_CONNECTION", "✅ Cliente gspread autorizado")
        sheets_status['authentication_ok'] = True
        
        spreadsheet_id = os.getenv('SPREADSHEET_ID')
        if not spreadsheet_id:
            raise Exception("SPREADSHEET_ID não encontrada")
        
        log_step("SHEETS_CONNECTION", f"Tentando acessar planilha: {spreadsheet_id}")
        
        spreadsheet = client.open_by_key(spreadsheet_id)
        log_step("SHEETS_CONNECTION", f"✅ Planilha acessada: {spreadsheet.title}")
        
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
# ROTAS PARA DEBUG DASHBOARD
# ================================

@app.route('/debug', methods=['GET'])
@app.route('/debug/', methods=['GET'])
def debug_dashboard():
    """Serve o dashboard de debug integrado"""
    
    debug_html = """
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔍 Google Sheets Debug Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.15);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
        }
        
        .header p {
            font-size: 1.1rem;
            opacity: 0.9;
        }
        
        .content {
            padding: 30px;
        }
        
        .nav-links {
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 30px;
            display: flex;
            justify-content: center;
            gap: 20px;
            flex-wrap: wrap;
        }
        
        .nav-link {
            background: #007bff;
            color: white;
            text-decoration: none;
            padding: 12px 24px;
            border-radius: 25px;
            transition: all 0.3s ease;
            font-weight: 600;
        }
        
        .nav-link:hover {
            background: #0056b3;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,123,255,0.3);
        }
        
        .server-config {
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            padding: 25px;
            border-radius: 15px;
            margin-bottom: 30px;
            border: 2px solid #dee2e6;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .current-url {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
            border-left: 4px solid #28a745;
            font-family: 'Monaco', 'Consolas', monospace;
            word-break: break-all;
        }
        
        .main-controls {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
            text-align: center;
        }
        
        .btn {
            background: linear-gradient(135deg, #007bff, #0056b3);
            color: white;
            border: none;
            padding: 18px 30px;
            border-radius: 30px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 700;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
            box-shadow: 0 4px 15px rgba(0,123,255,0.3);
        }
        
        .btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(0,123,255,0.4);
        }
        
        .btn:disabled {
            background: #6c757d;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        
        .btn.success {
            background: linear-gradient(135deg, #28a745, #20c997);
            box-shadow: 0 4px 15px rgba(40,167,69,0.3);
        }
        
        .btn.warning {
            background: linear-gradient(135deg, #ffc107, #ffb300);
            color: #212529;
            box-shadow: 0 4px 15px rgba(255,193,7,0.3);
        }
        
        .btn.danger {
            background: linear-gradient(135deg, #dc3545, #c82333);
            box-shadow: 0 4px 15px rgba(220,53,69,0.3);
        }
        
        .debug-section {
            margin: 25px 0;
            background: white;
            border-radius: 15px;
            overflow: hidden;
            border: 2px solid #e9ecef;
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
        }
        
        .debug-section:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 35px rgba(0,0,0,0.15);
        }
        
        .debug-header {
            background: linear-gradient(135deg, #495057, #343a40);
            color: white;
            padding: 20px 25px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .debug-header.success {
            background: linear-gradient(135deg, #28a745, #20c997);
        }
        
        .debug-header.error {
            background: linear-gradient(135deg, #dc3545, #c82333);
        }
        
        .debug-header.warning {
            background: linear-gradient(135deg, #ffc107, #ffb300);
            color: #212529;
        }
        
        .debug-header h3 {
            margin: 0;
            font-size: 1.3rem;
        }
        
        .debug-content {
            padding: 25px;
            max-height: 600px;
            overflow-y: auto;
        }
        
        .result-box {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 20px;
            margin: 15px 0;
            border-left: 5px solid #007bff;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .result-success {
            border-left-color: #28a745;
            background: linear-gradient(135deg, #f8fff9, #f0fff4);
        }
        
        .result-error {
            border-left-color: #dc3545;
            background: linear-gradient(135deg, #fff8f8, #fff5f5);
        }
        
        .json-viewer {
            background: #2d3748;
            color: #e2e8f0;
            padding: 20px;
            border-radius: 12px;
            font-family: 'Monaco', 'Consolas', monospace;
            font-size: 14px;
            overflow-x: auto;
            margin: 15px 0;
            line-height: 1.6;
        }
        
        .loading-spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #007bff;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            display: inline-block;
            margin: 20px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .loading-container {
            text-align: center;
            padding: 40px 20px;
        }
        
        .loading-text {
            margin-top: 15px;
            font-size: 16px;
            color: #6c757d;
        }
        
        @media (max-width: 768px) {
            .container {
                margin: 10px;
                border-radius: 15px;
            }
            
            .content {
                padding: 20px;
            }
            
            .main-controls {
                grid-template-columns: 1fr;
                gap: 15px;
            }
            
            .nav-links {
                flex-direction: column;
                align-items: center;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Google Sheets Debug Dashboard</h1>
            <p>Diagnóstico completo e teste de funcionalidades</p>
        </div>
        
        <div class="content">
            <!-- Navigation Links -->
            <div class="nav-links">
                <a href="/viewer" class="nav-link">📊 Data Viewer</a>
                <a href="/health" class="nav-link">💖 Health Check</a>
                <a href="/debug/logs" class="nav-link">📋 Logs</a>
                <a href="/" class="nav-link">🏠 Home</a>
            </div>
            
            <!-- Server Configuration -->
            <div class="server-config">
                <h3>🌐 Configuração do Servidor</h3>
                <div class="current-url">
                    <strong>🌐 URL Atual:</strong> <span id="currentUrl">{{ request.url_root }}</span>
                </div>
                <div class="current-url" style="margin-top: 10px;">
                    <strong>⏰ Última atualização:</strong> <span id="lastUpdate">{{ timestamp }}</span>
                </div>
            </div>
            
            <!-- Main Controls -->
            <div class="main-controls">
                <button class="btn" id="quickTestBtn">⚡ Teste Rápido</button>
                <button class="btn success" id="fullDebugBtn">🔍 Debug Completo</button>
                <button class="btn warning" id="testWriteBtn">✏️ Teste de Escrita</button>
                <button class="btn danger" id="clearResultsBtn">🗑️ Limpar Tudo</button>
            </div>
            
            <!-- Debug Sections -->
            <div class="debug-section">
                <div class="debug-header" id="healthHeader">
                    <h3>💖 Teste de Saúde do Servidor</h3>
                    <button class="btn" id="healthTestBtn">🔍 Testar</button>
                </div>
                <div class="debug-content" id="healthResult">
                    <p style="text-align: center; color: #6c757d; font-style: italic;">
                        Clique em "Testar" para verificar se o servidor está online e funcionando.
                    </p>
                </div>
            </div>
            
            <div class="debug-section">
                <div class="debug-header" id="envHeader">
                    <h3>🔧 Variáveis de Ambiente</h3>
                    <button class="btn" id="envTestBtn">🔍 Verificar</button>
                </div>
                <div class="debug-content" id="envResult">
                    <p style="text-align: center; color: #6c757d; font-style: italic;">
                        Verifica se as variáveis GOOGLE_SHEETS_CREDENTIALS e SPREADSHEET_ID estão configuradas corretamente.
                    </p>
                </div>
            </div>
            
            <div class="debug-section">
                <div class="debug-header" id="credsHeader">
                    <h3>🔐 Validação de Credenciais</h3>
                    <button class="btn" id="credsTestBtn">🔍 Validar</button>
                </div>
                <div class="debug-content" id="credsResult">
                    <p style="text-align: center; color: #6c757d; font-style: italic;">
                        Verifica se o JSON das credenciais do Google está no formato correto e contém todos os campos necessários.
                    </p>
                </div>
            </div>
            
            <div class="debug-section">
                <div class="debug-header" id="sheetsHeader">
                    <h3>📊 Conexão Google Sheets</h3>
                    <button class="btn" id="sheetsTestBtn">🔍 Testar</button>
                </div>
                <div class="debug-content" id="sheetsResult">
                    <p style="text-align: center; color: #6c757d; font-style: italic;">
                        Testa a autenticação completa com o Google Sheets API e verifica o acesso à planilha.
                    </p>
                </div>
            </div>
            
            <div class="debug-section">
                <div class="debug-header" id="writeHeader">
                    <h3>✏️ Teste de Escrita</h3>
                    <button class="btn" id="writeTestBtn">✏️ Escrever Teste</button>
                </div>
                <div class="debug-content" id="writeResult">
                    <p style="text-align: center; color: #6c757d; font-style: italic;">
                        Escreve dados de teste na planilha para verificar se as permissões de escrita estão funcionando.
                    </p>
                </div>
            </div>
        </div>
    </div>

    <script>
        const SERVER_URL = window.location.origin;
        
        function showLoading(containerId, message = 'Carregando...') {
            const container = document.getElementById(containerId);
            container.innerHTML = `
                <div class="loading-container">
                    <div class="loading-spinner"></div>
                    <div class="loading-text">${message}</div>
                </div>
            `;
        }
        
        function showResult(containerId, result, type = 'info') {
            const container = document.getElementById(containerId);
            const header = document.getElementById(containerId.replace('Result', 'Header'));
            
            header.className = `debug-header ${type}`;
            
            let content = '';
            if (typeof result === 'object') {
                content = `
                    <div class="result-box result-${type}">
                        <div class="json-viewer">${JSON.stringify(result, null, 2)}</div>
                    </div>
                `;
            } else {
                content = `
                    <div class="result-box result-${type}">
                        <p>${result}</p>
                    </div>
                `;
            }
            container.innerHTML = content;
        }
        
        async function makeRequest(endpoint, method = 'GET', data = null) {
            try {
                const config = {
                    method: method,
                    headers: {
                        'Content-Type': 'application/json',
                    }
                };
                
                if (data) {
                    config.body = JSON.stringify(data);
                }
                
                const response = await fetch(`${SERVER_URL}${endpoint}`, config);
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                return await response.json();
            } catch (error) {
                throw new Error(`Erro de conexão: ${error.message}`);
            }
        }
        
        // Event Listeners
        document.getElementById('healthTestBtn').addEventListener('click', async () => {
            showLoading('healthResult', 'Verificando saúde do servidor...');
            try {
                const result = await makeRequest('/health');
                showResult('healthResult', result, 'success');
            } catch (error) {
                showResult('healthResult', { error: error.message }, 'error');
            }
        });
        
        document.getElementById('envTestBtn').addEventListener('click', async () => {
            showLoading('envResult', 'Verificando variáveis de ambiente...');
            try {
                const result = await makeRequest('/debug/environment');
                const type = result.environment_variables.all_found ? 'success' : 'error';
                showResult('envResult', result, type);
            } catch (error) {
                showResult('envResult', { error: error.message }, 'error');
            }
        });
        
        document.getElementById('credsTestBtn').addEventListener('click', async () => {
            showLoading('credsResult', 'Validando credenciais...');
            try {
                const result = await makeRequest('/debug/credentials');
                const type = result.success ? 'success' : 'error';
                showResult('credsResult', result, type);
            } catch (error) {
                showResult('credsResult', { error: error.message }, 'error');
            }
        });
        
        document.getElementById('sheetsTestBtn').addEventListener('click', async () => {
            showLoading('sheetsResult', 'Testando conexão com Google Sheets...');
            try {
                const result = await makeRequest('/debug/sheets');
                const type = result.success ? 'success' : 'error';
                showResult('sheetsResult', result, type);
            } catch (error) {
                showResult('sheetsResult', { error: error.message }, 'error');
            }
        });
        
        document.getElementById('writeTestBtn').addEventListener('click', async () => {
            showLoading('writeResult', 'Testando escrita na planilha...');
            try {
                const result = await makeRequest('/debug/test-write');
                const type = result.success ? 'success' : 'error';
                showResult('writeResult', result, type);
            } catch (error) {
                showResult('writeResult', { error: error.message }, 'error');
            }
        });
        
        document.getElementById('fullDebugBtn').addEventListener('click', async () => {
            showLoading('healthResult', 'Executando debug completo...');
            try {
                const result = await makeRequest('/debug/full');
                const type = result.success ? 'success' : 'error';
                showResult('healthResult', result, type);
            } catch (error) {
                showResult('healthResult', { error: error.message }, 'error');
            }
        });
        
        document.getElementById('clearResultsBtn').addEventListener('click', () => {
            const containers = ['healthResult', 'envResult', 'credsResult', 'sheetsResult', 'writeResult'];
            containers.forEach(containerId => {
                const container = document.getElementById(containerId);
                const header = document.getElementById(containerId.replace('Result', 'Header'));
                
                container.innerHTML = `
                    <p style="text-align: center; color: #6c757d; font-style: italic;">
                        Clique no botão para executar o teste.
                    </p>
                `;
                header.className = 'debug-header';
            });
        });
    </script>
</body>
</html>
    """
    
    return render_template_string(debug_html, 
                                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                request=request)

# ================================
# ROTAS PARA DATA VIEWER
# ================================

@app.route('/viewer', methods=['GET'])
@app.route('/viewer/', methods=['GET'])
def data_viewer():
    """Serve o dashboard de visualização de dados"""
    
    viewer_html = """
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📊 Google Sheets Data Viewer</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.15);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
        }
        
        .content {
            padding: 30px;
        }
        
        .nav-links {
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 30px;
            display: flex;
            justify-content: center;
            gap: 20px;
            flex-wrap: wrap;
        }
        
        .nav-link {
            background: #007bff;
            color: white;
            text-decoration: none;
            padding: 12px 24px;
            border-radius: 25px;
            transition: all 0.3s ease;
            font-weight: 600;
        }
        
        .nav-link:hover {
            background: #0056b3;
            transform: translateY(-2px);
        }
        
        .controls {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .select-group, .action-group {
            display: flex;
            flex-direction: column;
        }
        
        .select-group label, .action-group label {
            font-weight: 600;
            margin-bottom: 8px;
            color: #495057;
        }
        
        select {
            padding: 12px;
            border-radius: 8px;
            border: 1px solid #ced4da;
            font-size: 16px;
            background-color: #f8f9fa;
        }
        
        .btn {
            background: linear-gradient(135deg, #007bff, #0056b3);
            color: white;
            border: none;
            padding: 15px 25px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 700;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
            box-shadow: 0 4px 15px rgba(0,123,255,0.3);
            margin-top: 25px;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,123,255,0.4);
        }
        
        .btn:disabled {
            background: #6c757d;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        
        .table-container {
            overflow-x: auto;
            background: #f8f9fa;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }
        
        th, td {
            text-align: left;
            padding: 12px 15px;
            border-bottom: 1px solid #dee2e6;
        }
        
        th {
            background-color: #e9ecef;
            color: #495057;
            font-weight: 700;
            text-transform: uppercase;
        }
        
        tr:nth-child(even) {
            background-color: #f6f6f6;
        }
        
        .alert-message {
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
            font-weight: 600;
            display: none;
        }
        
        .alert-success {
            background-color: #d4edda;
            color: #155724;
        }
        
        .alert-danger {
            background-color: #f8d7da;
            color: #721c24;
        }
        
        .loading-container {
            text-align: center;
            padding: 40px 20px;
        }
        
        .loading-spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #007bff;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            display: inline-block;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .loading-text {
            margin-top: 15px;
            font-size: 16px;
            color: #6c757d;
        }
        
        @media (max-width: 768px) {
            .container {
                margin: 10px;
                border-radius: 15px;
            }
            .content {
                padding: 20px;
            }
            .controls {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Google Sheets Data Viewer</h1>
            <p>Selecione uma aba para visualizar o conteúdo</p>
        </div>
        
        <div class="content">
            <div class="nav-links">
                <a href="/debug" class="nav-link">🔍 Debug Dashboard</a>
                <a href="/health" class="nav-link">💖 Health Check</a>
                <a href="/debug/logs" class="nav-link">📋 Logs</a>
                <a href="/" class="nav-link">🏠 Home</a>
            </div>

            <div class="controls">
                <div class="select-group">
                    <label for="sheetSelect">Selecione a Aba:</label>
                    <select id="sheetSelect">
                        <option value="">Carregando...</option>
                    </select>
                </div>
                <div class="action-group">
                    <button class="btn" id="loadDataBtn">Carregar Dados</button>
                    <button class="btn" id="downloadCsvBtn">Baixar CSV</button>
                </div>
            </div>

            <div id="alertMessage" class="alert-message"></div>

            <div id="tableContainer" class="table-container">
                <div class="loading-container" id="initialLoad">
                    <div class="loading-spinner"></div>
                    <div class="loading-text">Carregando abas da planilha...</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const SERVER_URL = window.location.origin;
        const sheetSelect = document.getElementById('sheetSelect');
        const loadDataBtn = document.getElementById('loadDataBtn');
        const downloadCsvBtn = document.getElementById('downloadCsvBtn');
        const tableContainer = document.getElementById('tableContainer');
        const alertMessage = document.getElementById('alertMessage');
        const initialLoad = document.getElementById('initialLoad');

        async function showAlert(message, type = 'danger') {
            alertMessage.textContent = message;
            alertMessage.className = `alert-message alert-${type}`;
            alertMessage.style.display = 'block';
            setTimeout(() => {
                alertMessage.style.display = 'none';
            }, 5000);
        }

        async function fetchWorksheets() {
            try {
                const response = await fetch(`${SERVER_URL}/api/worksheets`);
                if (!response.ok) {
                    throw new Error('Erro ao carregar as abas da planilha.');
                }
                const data = await response.json();
                
                sheetSelect.innerHTML = '';
                if (data.worksheets && data.worksheets.length > 0) {
                    data.worksheets.forEach(sheetName => {
                        const option = document.createElement('option');
                        option.value = sheetName;
                        option.textContent = sheetName;
                        sheetSelect.appendChild(option);
                    });
                    loadDataBtn.disabled = false;
                    downloadCsvBtn.disabled = false;
                    initialLoad.style.display = 'none';
                } else {
                    sheetSelect.innerHTML = '<option value="">Nenhuma aba encontrada</option>';
                    loadDataBtn.disabled = true;
                    downloadCsvBtn.disabled = true;
                    showAlert('Nenhuma aba encontrada na planilha. Verifique a configuração.', 'warning');
                }
            } catch (error) {
                showAlert(error.message || 'Erro de conexão com a API.', 'danger');
                sheetSelect.innerHTML = '<option value="">Erro ao carregar</option>';
                loadDataBtn.disabled = true;
                downloadCsvBtn.disabled = true;
            }
        }

        async function loadSheetData() {
            const sheetName = sheetSelect.value;
            if (!sheetName) {
                showAlert('Por favor, selecione uma aba para carregar.', 'warning');
                return;
            }

            tableContainer.innerHTML = `<div class="loading-container"><div class="loading-spinner"></div><div class="loading-text">Carregando dados de "${sheetName}"...</div></div>`;

            try {
                const response = await fetch(`${SERVER_URL}/api/data?sheet_name=${encodeURIComponent(sheetName)}`);
                if (!response.ok) {
                    throw new Error('Erro ao carregar os dados da aba.');
                }
                const data = await response.json();
                
                if (data.error) {
                    throw new Error(data.error);
                }

                if (data.data && data.data.length > 0) {
                    renderTable(data.data);
                    showAlert(`Dados de "${sheetName}" carregados com sucesso!`, 'success');
                } else {
                    tableContainer.innerHTML = '<p style="text-align: center; color: #6c757d; font-style: italic;">Nenhum dado encontrado nesta aba.</p>';
                    showAlert(`A aba "${sheetName}" está vazia.`, 'warning');
                }

            } catch (error) {
                tableContainer.innerHTML = `<p style="text-align: center; color: #dc3545;">Erro: ${error.message}</p>`;
                showAlert(error.message, 'danger');
            }
        }

        function renderTable(data) {
            if (!data || data.length === 0) {
                tableContainer.innerHTML = '<p style="text-align: center; color: #6c757d; font-style: italic;">Nenhum dado para exibir.</p>';
                return;
            }

            let tableHtml = '<table><thead><tr>';
            const headers = data[0];
            headers.forEach(header => {
                tableHtml += `<th>${header}</th>`;
            });
            tableHtml += '</tr></thead><tbody>';

            data.slice(1).forEach(row => {
                tableHtml += '<tr>';
                row.forEach(cell => {
                    tableHtml += `<td>${cell}</td>`;
                });
                tableHtml += '</tr>';
            });
            
            tableHtml += '</tbody></table>';
            tableContainer.innerHTML = tableHtml;
        }

        // Event Listeners
        loadDataBtn.addEventListener('click', loadSheetData);
        downloadCsvBtn.addEventListener('click', () => {
            const sheetName = sheetSelect.value;
            if (sheetName) {
                window.location.href = `${SERVER_URL}/api/download-csv?sheet_name=${encodeURIComponent(sheetName)}`;
            } else {
                showAlert('Por favor, selecione uma aba para baixar.', 'warning');
            }
        });

        // Initial load
        document.addEventListener('DOMContentLoaded', fetchWorksheets);

    </script>
</body>
</html>
    """
    
    return render_template_string(viewer_html)