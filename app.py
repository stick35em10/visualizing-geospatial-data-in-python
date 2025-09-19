import os
import json
import logging
import base64
import re
import uuid
import io
import unicodedata
from datetime import datetime
from urllib.parse import quote

from flask import Flask, request, jsonify
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials
from google.auth.exceptions import GoogleAuthError
from PIL import Image
import requests
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError

# OpenTelemetry imports
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry._logs import set_logger_provider

# Cloudinary imports
import cloudinary
import cloudinary.uploader
import cloudinary.api
from cloudinary.utils import cloudinary_url

# Initialize OpenTelemetry
def init_opentelemetry():
    """Initialize OpenTelemetry tracing and logging"""
    try:
        # Set up tracing
        resource = Resource.create({
            "service.name": "sheets-app-api",
            "service.version": "1.0.0",
            "deployment.environment": os.getenv("ENVIRONMENT", "production")
        })
        
        trace.set_tracer_provider(TracerProvider(resource=resource))
        
        # OTLP exporter for traces
        otlp_exporter = OTLPSpanExporter(
            endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces"),
        )
        
        span_processor = BatchSpanProcessor(otlp_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)
        
        # Set up logging
        logger_provider = LoggerProvider(resource=resource)
        set_logger_provider(logger_provider)
        
        otlp_log_exporter = OTLPLogExporter(
            endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/logs"),
        )
        
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_log_exporter))
        
        # Add OTLP handler to root logger
        handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
        logging.getLogger().addHandler(handler)
        
        logging.info("OpenTelemetry initialized successfully")
        
    except Exception as e:
        logging.warning(f"OpenTelemetry initialization failed: {str(e)}")

# Initialize OpenTelemetry
init_opentelemetry()

# Get tracer
tracer = trace.get_tracer(__name__)

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True
)

# Configuração de logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
app = Flask(__name__)



@app.route('/api/test')
def test_endpoint():
    logger.info("Endpoint test chamado", extra={
        "user_agent": request.headers.get('User-Agent'),
        "client_ip": request.remote_addr,
        "endpoint": "/api/test"
    })
    
    try:
        # Sua lógica aqui
        logger.debug("Processando requisição")
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error("Erro no endpoint test", exc_info=True, extra={
            "error_type": type(e).__name__,
            "error_message": str(e)
        })
        return jsonify({"error": str(e)}), 500



# Instrument Flask and Requests
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

# Configuração CORS correta - APENAS ESTA
CORS(app, 
    origins=[
        "https://stick35em10.github.io",
        "http://localhost:*",
        "http://127.0.0.1:*",
        "https://*.github.io",
        
        "http://localhost:5500",  # ADICIONE esta linha
        "http://127.0.0.1:5500"
    ],
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization", "Accept"],  # ADICIONE "Accept"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    expose_headers=["Content-Type"],
    max_age=3600
)


# Adicione este handler manual para OPTIONS
"""@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = jsonify({"status": "ok"})
        response.headers.add("Access-Control-Allow-Origin", "https://stick35em10.github.io")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization,Accept")
        response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
        response.headers.add("Access-Control-Allow-Credentials", "true")
        return response
   """ 
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
"""
# Por esta configuração mais permissiva (para desenvolvimento):
# from flask_cors import CORS

# Configuração CORS mais permissiva
""" 
""" 
CORS(app, origins=[
    "https://stick35em10.github.io",
    "http://localhost:*",
    "http://127.0.0.1:*",
    "https://*.github.io"
])"""

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

SHARED_DRIVE_ID = '1T3bLqnSCLg3_zkqnj5JXzH8tvN-h63yy'

def log_step(step, message, success=True):
    #Registra cada passo com timestamp"""
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
    
    with tracer.start_as_current_span("get_sheets_client") as span:
        try:
            # Verifica se já temos um cliente em cache
            if _client_cache is not None:
                span.set_attribute("cache.hit", True)
                return _client_cache, _spreadsheet_cache
            
            span.set_attribute("cache.hit", False)
            
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
                'https://www.googleapis.com/auth/drive',
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
            
            span.set_attribute("spreadsheet.title", spreadsheet.title)
            span.set_attribute("spreadsheet.id", spreadsheet_id)
            
            log_step("SHEETS_CLIENT", f"✅ Cliente conectado à planilha: {spreadsheet.title}")
            
            return client, spreadsheet
            
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            log_step("SHEETS_CLIENT", f"❌ Erro ao conectar: {str(e)}", False)
            raise

def check_environment_variables():
    """Verifica se as variáveis de ambiente estão definidas"""
    with tracer.start_as_current_span("check_environment_variables"):
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
    with tracer.start_as_current_span("parse_credentials") as span:
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
            
            span.set_attribute("credentials.project_id", creds_dict.get('project_id'))
            span.set_attribute("credentials.client_email", creds_dict.get('client_email'))
            
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
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, error_msg))
            log_step("CREDENTIALS_PARSE", error_msg, False)
            return {'success': False, 'error': error_msg, 'type': 'json_parse_error'}
        
        except Exception as e:
            error_msg = f"❌ Erro nas credenciais: {str(e)}"
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, error_msg))
            log_step("CREDENTIALS_PARSE", error_msg, False)
            return {'success': False, 'error': error_msg, 'type': 'credentials_error'}

def test_google_sheets_connection():
    """Testa a conexão completa com o Google Sheets"""
    with tracer.start_as_current_span("test_google_sheets_connection") as span:
        log_step("SHEETS_CONNECTION", "📊 Testando conexão com Google Sheets...")
        
        try:
            client, spreadsheet = get_sheets_client()
            
            # Listar abas da planilha
            worksheets = spreadsheet.worksheets()
            worksheet_names = [ws.title for ws in worksheets]
            
            span.set_attribute("spreadsheet.worksheet_count", len(worksheets))
            span.set_attribute("spreadsheet.worksheet_names", str(worksheet_names))
            
            log_step("SHEETS_CONNECTION", f"📄 Abas encontradas: {worksheet_names}")
            
            # Testar leitura da primeira aba
            if worksheets:
                first_sheet = worksheets[0]
                try:
                    sample_data = first_sheet.get('A1:E5')
                    span.set_attribute("spreadsheet.sample_data_rows", len(sample_data))
                    log_step("SHEETS_CONNECTION", f"✅ Teste de leitura OK. {len(sample_data)} linhas encontradas")
                except Exception as read_error:
                    span.record_exception(read_error)
                    log_step("SHEETS_CONNECTION", f"⚠️ Aviso: Erro ao ler dados: {read_error}")
            
            sheets_status['spreadsheet_accessible'] = True
            sheets_status['initialized'] = True
            sheets_status['authentication_ok'] = True
            sheets_status['last_test_time'] = datetime.now().isoformat()
            
            span.set_attribute("connection.success", True)
            
            return {
                'success': True,
                'spreadsheet_id': os.getenv('SPREADSHEET_ID'),
                'spreadsheet_title': spreadsheet.title,
                'worksheet_names': worksheet_names,
                'test_time': sheets_status['last_test_time']
            }
            
        except Exception as e:
            error_msg = f"❌ Erro de conexão: {str(e)}"
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, error_msg))
            log_step("SHEETS_CONNECTION", error_msg, False)
            return {'success': False, 'error': error_msg}

def sanitize_filename(filename):
    """Sanitize filename for Cloudinary upload"""
    with tracer.start_as_current_span("sanitize_filename") as span:
        span.set_attribute("filename.original", filename)
        
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
        
        span.set_attribute("filename.sanitized", filename)
        
        return filename

def upload_to_cloudinary(file_content, original_filename):
    """Upload file to Cloudinary with proper URL generation"""
    with tracer.start_as_current_span("upload_to_cloudinary") as span:
        span.set_attribute("file.filename", original_filename)
        span.set_attribute("file.size", len(file_content))
        
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
            
            span.set_attribute("cloudinary.public_id", public_id)
            log_step("CLOUDINARY_UPLOAD", f"Uploading with public_id: {public_id}")
            
            # Upload to Cloudinary
            upload_result = cloudinary.uploader.upload(
                file_content,
                public_id=public_id,
                folder="sheets_app",
                resource_type="auto",
                overwrite=True,
                quality="auto",
                fetch_format="auto"
            )
            
            # Get the secure URL (HTTPS)
            image_url = upload_result.get('secure_url')
            
            if not image_url:
                raise Exception("Cloudinary não retornou URL da imagem")
            
            span.set_attribute("cloudinary.url", image_url)
            span.set_attribute("cloudinary.upload_success", True)
            log_step("CLOUDINARY_UPLOAD", f"✅ Upload concluído: {image_url}")
            
            return image_url
            
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            log_step("CLOUDINARY_UPLOAD", f"❌ Erro no upload: {str(e)}", False)
            raise Exception(f"Erro no upload para Cloudinary: {str(e)}")

# 16.09, 18:44, 2. Crie funções internas para as rotas de debug:
def debug_sheets_internal():
    """Versão interna de debug_sheets que retorna dicionário"""
    try:
        # Verificar variáveis de ambiente
        env_check = check_environment_variables()
        
        # Verificar credenciais
        creds_check = parse_credentials()
        
        # Testar conexão
        connection_test = None
        if env_check['all_found'] and creds_check['success']:
            try:
                connection_test = test_google_sheets_connection()
            except Exception as conn_error:
                connection_test = {'success': False, 'error': str(conn_error)}
        
        # Informações do cache
        cache_info = {
            'client_cached': _client_cache is not None,
            'spreadsheet_cached': _spreadsheet_cache is not None
        }
        
        return {
            'environment_check': env_check,
            'credentials_check': creds_check,
            'connection_test': connection_test,
            'cache_info': cache_info,
            'status': sheets_status
        }
        
    except Exception as e:
        return {'error': f'Erro no debug do Sheets: {str(e)}'}

def debug_cloudinary_internal():
    """Versão interna de debug_cloudinary que retorna dicionário"""
    try:
        # Verificar configuração básica
        config_status = {
            'cloud_name': bool(os.getenv('CLOUDINARY_CLOUD_NAME')),
            'api_key': bool(os.getenv('CLOUDINARY_API_KEY')),
            'api_secret': bool(os.getenv('CLOUDINARY_API_SECRET')),
            'fully_configured': all([
                os.getenv('CLOUDINARY_CLOUD_NAME'),
                os.getenv('CLOUDINARY_API_KEY'),
                os.getenv('CLOUDINARY_API_SECRET')
            ])
        }
        
        # Testar conexão simples (sem fazer upload real)
        test_result = None
        if config_status['fully_configured']:
            try:
                # Teste simples da API
                result = cloudinary.api.ping()
                test_result = {
                    'status': result.get('status') if result else 'unknown',
                    'success': result is not None
                }
            except Exception as e:
                test_result = {
                    'success': False,
                    'error': str(e)
                }
        
        return {
            'configuration': config_status,
            'connection_test': test_result
        }
        
    except Exception as e:
        return {'error': f'Erro ao verificar Cloudinary: {str(e)}'}

def debug_credentials_internal():
    """Versão interna de debug_credentials que retorna dicionário"""
    try:
        # Verificar se as credenciais estão presentes
        creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
        creds_present = creds_json is not None and len(creds_json.strip()) > 0
        
        # Verificar formato básico
        format_valid = False
        is_base64 = False
        project_id = None
        client_email = None
        
        if creds_present:
            try:
                # Verificar se é base64
                test_creds = creds_json.strip()
                if test_creds.startswith('eyJ'):  # JWT normalmente começa com eyJ
                    try:
                        decoded = base64.b64decode(test_creds).decode('utf-8')
                        is_base64 = True
                        test_creds = decoded
                    except:
                        pass
                
                # Tentar fazer parse do JSON
                creds_dict = json.loads(test_creds)
                format_valid = True
                
                # Extrair informações não sensíveis
                project_id = creds_dict.get('project_id')
                client_email = creds_dict.get('client_email')
                
            except (json.JSONDecodeError, UnicodeDecodeError):
                format_valid = False
        
        # Verificar Cloudinary
        cloudinary_configured = all([
            os.getenv('CLOUDINARY_CLOUD_NAME'),
            os.getenv('CLOUDINARY_API_KEY'), 
            os.getenv('CLOUDINARY_API_SECRET')
        ])
        
        return {
            'google_sheets': {
                'credentials_present': creds_present,
                'format_valid': format_valid,
                'is_base64_encoded': is_base64,
                'project_id': project_id,
                'client_email': client_email,
                'status': sheets_status
            },
            'cloudinary': {
                'configured': cloudinary_configured,
                'cloud_name': bool(os.getenv('CLOUDINARY_CLOUD_NAME')),
                'api_key': bool(os.getenv('CLOUDINARY_API_KEY')),
                'api_secret': bool(os.getenv('CLOUDINARY_API_SECRET'))
            }
        }
        
    except Exception as e:
        return {'error': f'Erro ao verificar credenciais: {str(e)}'}

def debug_environment_internal():
    """Versão interna de debug_environment que retorna dicionário"""
    try:
        # Lista de variáveis sensíveis que não devem ser expostas
        sensitive_keys = [
            'GOOGLE_SHEETS_CREDENTIALS', 'CLOUDINARY_API_SECRET', 
            'API_KEY', 'SECRET_KEY', 'PASSWORD', 'TOKEN', 'PRIVATE_KEY'
        ]
        
        env_vars = {}
        for key, value in os.environ.items():
            # Ocultar valores de variáveis sensíveis
            if any(sensitive in key.upper() for sensitive in sensitive_keys):
                env_vars[key] = '*** HIDDEN ***'
            else:
                env_vars[key] = value
        
        return {
            'environment_variables': env_vars,
            'sensitive_keys_filtered': sensitive_keys
        }
        
    except Exception as e:
        return {'error': f'Erro ao coletar variáveis de ambiente: {str(e)}'}

# 18.09, 16:00 Para calcular e gravar o Saldo Atual com base em entradas, saídas e o saldo anterior, você precisa modificar sua aplicação para incluir essa lógica. Aqui está uma implementação completa:
# 1. Primeiro, adicione esta função auxiliar no seu código:
def calculate_current_balance(spreadsheet, worksheet_name):
    """Calcula o saldo atual baseado nos dados existentes"""
    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
        records = worksheet.get_all_records()
        
        if not records:
            return 0.0  # Saldo inicial zero se não houver registros
        # Ordenar por timestamp se existir a coluna
        if 'timestamp' in records[0]:
            records.sort(key=lambda x: x.get('timestamp', ''))
            
        for record in reversed(records):  # Começar do último registro
            saldo_atual = record.get('Saldo Atual', '')
            
            # Verificar se tem saldo válido (não vazio e numérico)
            if saldo_atual and str(saldo_atual).strip() and str(saldo_atual).replace('.', '').isdigit():
                try:
                    last_valid_balance = float(saldo_atual)
                    break
                except ValueError:
                    continue
        
        return last_valid_balance
    
        """
        # Calcular saldo acumulado
        current_balance = 0.0
        for record in records:
            entrada = float(record.get('Entrada', 0) or 0)
            saida = float(record.get('Saída', 0) or 0)
            saldo_anterior = float(record.get('Saldo Anterior', 0) or 0)
            
            # Se já tem saldo calculado, usar como base
            if record.get('Saldo Atual'):
                current_balance = float(record.get('Saldo Atual', 0))
            else:
                # Calcular novo saldo
                current_balance = saldo_anterior + entrada - saida
        
        return current_balance
        """
    except Exception as e:
        logger.error(f"Erro ao calcular saldo: {str(e)}")
        return 0.0
    
#2. Adicionar middleware manual para CORS
"""
@app.after_request
def after_request(response):
    
    response.headers.add('Access-Control-Allow-Origin', 'https://stick35em10.github.io')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

@app.before_request
def handle_preflight():
    #Lida com requisições OPTIONS (preflight)
    if request.method == "OPTIONS":
        response = jsonify({"status": "ok"})
        response.headers.add('Access-Control-Allow-Origin', 'https://stick35em10.github.io')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response
"""
# Adicione este handler manual para OPTIONS para garantir o tratamento de preflight
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = jsonify({"status": "ok"})
        response.headers.add("Access-Control-Allow-Origin", request.headers.get('Origin', '*'))
        response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization,Accept")
        response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
        response.headers.add("Access-Control-Allow-Credentials", "true")
        return response
    
# ROTAS DE API


@app.route('/api/sheets/worksheets', methods=['GET'])
def get_worksheets():
    """Endpoint para obter a lista de worksheets da planilha"""
    with tracer.start_as_current_span("get_worksheets"):
        try:
            if not sheets_status['initialized']:
                # Tenta reconectar se não estiver inicializado
                try:
                    test_google_sheets_connection()
                except Exception as e:
                    return jsonify({
                        'success': False,
                        'error': f'Erro de conexão: {str(e)}'
                    }), 500
            
            client, spreadsheet = get_sheets_client()
            
            # Listar todas as worksheets
            worksheets = spreadsheet.worksheets()
            
            worksheet_info = []
            for ws in worksheets:
                try:
                    # Obter informações básicas de cada worksheet
                    row_count = ws.row_count
                    col_count = ws.col_count
                    
                    worksheet_info.append({
                        'title': ws.title,
                        'row_count': row_count,
                        'col_count': col_count,
                        'index': ws.index,
                        'id': ws.id
                    })
                except Exception as e:
                    # Se houver erro em uma worksheet, continuar com as outras
                    worksheet_info.append({
                        'title': ws.title,
                        'row_count': 0,
                        'col_count': 0,
                        'error': str(e)
                    })
            
            return jsonify({
                'success': True,
                'spreadsheet_title': spreadsheet.title,
                'spreadsheet_id': os.getenv('SPREADSHEET_ID'),
                'worksheets': worksheet_info,
                'total_worksheets': len(worksheets)
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Erro ao obter worksheets: {str(e)}'
            }), 500
            
# Endpoint local para teste CORS
@app.route('/debug/cors-test', methods=['GET', 'OPTIONS'])
def local_cors_test():
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'preflight ok'})
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:5500')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,OPTIONS')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response
    
    return jsonify({
        'message': 'Local CORS test successful',
        'origin': request.headers.get('Origin'),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/debug/cors', methods=['GET', 'OPTIONS'])
def debug_cors():
    """Endpoint para debug de CORS"""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        return response
    
    return jsonify({
        'origin': request.headers.get('Origin'),
        'cors_headers': {
            'Access-Control-Allow-Origin': request.headers.get('Access-Control-Allow-Origin'),
            'Access-Control-Allow-Methods': request.headers.get('Access-Control-Allow-Methods'),
            'Access-Control-Allow-Headers': request.headers.get('Access-Control-Allow-Headers')
        }
    })
    
@app.route('/images', methods=['GET'])
def get_images():
    """Endpoint para obter imagens da planilha"""
    with tracer.start_as_current_span("get_images"):
        try:
            if not sheets_status['initialized']:
                # Tenta reconectar se não estiver inicializado
                try:
                    test_google_sheets_connection()
                except:
                    pass
                
            client, spreadsheet = get_sheets_client()
            worksheet = spreadsheet.worksheet('Imagens')
            
            # Obter todos os dados da worksheet
            data = worksheet.get_all_records()
            
            # Transformar os dados para o formato esperado pelo frontend
            formatted_data = []
            for row in data:
                # Usar o campo correto do Google Sheets: "URL da Imagem"
                image_url = row.get('URL da Imagem', '') or row.get('url_link', '') or row.get('link', '')
                
                if row.get('URL da Imagem'):  # Verificar se tem URL
                    formatted_data.append({
                        'id': row.get('ID Único', str(uuid.uuid4())[:8]),
                        'filename': row.get('Nome do Arquivo Original', ''),
                        'file_size': len(row.get('URL da Imagem', '')),  # Aproximação
                        'upload_date': image_url, #row.get('Data', ''),
                        
                        'url': row.get('URL da Imagem', ''),
                        
                        'thumbnail_path': row.get('URL da Imagem', ''),  # Usar mesma URL para thumbnail
                        'file_path': row.get('URL da Imagem', ''),
                        'location': {
                            'lat': float(row.get('Latitude', 0)) if row.get('Latitude') else 0,
                            'lng': float(row.get('Longitude', 0)) if row.get('Longitude') else 0
                        } if row.get('Latitude') and row.get('Longitude') else None
                    })
                    
            return jsonify(formatted_data)
            
        except Exception as e:
            #return jsonify({
            #    'success': False,
            #    'error': f'Erro ao carregar imagens: {str(e)}'
            #}), 500
            
            # Retorna array vazio em vez de erro para não quebrar o frontend
            logger.error(f"Erro ao carregar imagens: {str(e)}")
            return jsonify([])

@app.route('/debug/images', methods=['GET'])
def debug_images():
    """Endpoint para debug da estrutura de imagens"""
    with tracer.start_as_current_span("debug_images"):
        try:
            client, spreadsheet = get_sheets_client()
            worksheet = spreadsheet.worksheet('Imagens')
            
            # Obter cabeçalhos para verificar a estrutura
            headers = worksheet.row_values(1)
            
            # Obter algumas linhas de exemplo
            sample_data = worksheet.get_all_records()
            
            return jsonify({
                'headers': headers,
                'sample_data': sample_data[:3],  # Primeiras 3 linhas
                'total_records': len(sample_data)
            }), 200
            
        except Exception as e:
            return jsonify({
                'error': f'Erro ao debug imagens: {str(e)}'
            }), 500

#6. Adicionar Rota /upload que está sendo chamada pelo frontend
# Problema: O frontend tenta POST para /upload mas a rota no Flask é /api/upload/photos.
# Adicionar alias para a rota de upload
@app.route('/upload', methods=['POST', 'OPTIONS'])
@app.route('/api/upload/photos', methods=['POST', 'OPTIONS'])
def upload_photos():
    """Endpoint completo para upload de fotos com armazenamento no Cloudinary"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    with tracer.start_as_current_span("upload_photos") as span:
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
            
            span.set_attribute("upload.title", title)
            span.set_attribute("upload.worksheet", worksheet_name)
            #span.set_attribute("upload.files_count", len(request.files.getlist('photos')))
            
            # Processar arquivos
            # Processar arquivos - compatibilidade com ambos os nomes de campo
            #uploaded_files = request.files.getlist('photos')
            uploaded_files = []
            if 'photos' in request.files:
                uploaded_files = request.files.getlist('photos')
            elif 'files' in request.files:
                uploaded_files = request.files.getlist('files')
            
            file_count = len(uploaded_files)
            span.set_attribute("upload.files_count", file_count)
            
            
            if file_count == 0:
                span.set_status(trace.Status(trace.StatusCode.ERROR, "No files uploaded"))
                return jsonify({
                    'success': False,
                    'error': 'Nenhum arquivo enviado'
                }), 400
                
            
            log_step("UPLOAD_PHOTOS", f"Processando {file_count} arquivo(s) para a aba '{worksheet_name}'")
            
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
                        with tracer.start_as_current_span("process_file") as file_span:
                            file_span.set_attribute("file.index", i)
                            file_span.set_attribute("file.name", file.filename)
                            
                            # Ler o arquivo
                            file_content = file.read()
                            filename = file.filename
                            sanitized_filename = sanitize_filename(filename)
                            file_size = len(file_content)
                            unique_id = str(uuid.uuid4())[:8]
                            
                            file_span.set_attribute("file.size", file_size)
                            file_span.set_attribute("file.sanitized_name", sanitized_filename)
                            
                            log_step("UPLOAD_PHOTOS", f"Processando arquivo {i+1}: {filename} -> {sanitized_filename} ({file_size} bytes)")
                            
                            # Verificar tamanho do arquivo (limite de 10MB para Cloudinary)
                            if file_size > 10 * 1024 * 1024:
                                raise Exception(f"Arquivo muito grande: {file_size} bytes (limite: 10MB)")
                            
                            # Processar a imagem para obter metadados
                            try:
                                image = Image.open(io.BytesIO(file_content))
                                width, height = image.size
                                image_format = image.format
                                file_span.set_attribute("image.dimensions", f"{width}x{height}")
                                file_span.set_attribute("image.format", image_format)
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
                                sanitized_filename,
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
            
            span.set_attribute("upload.successful", successful_uploads)
            span.set_attribute("upload.failed", failed_uploads)
            
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
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            error_msg = f"⚠ Erro no upload de fotos: {str(e)}"
            log_step("UPLOAD_PHOTOS", error_msg, False)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

# ... (mantenha as outras rotas existentes, adicionando tracing onde necessário)

# Modificar a função health_check para ser mais tolerante
@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint de health check para o Render"""
    with tracer.start_as_current_span("health_check"):
        try:
            # Verificação básica de saúde
            # Verificação mais tolerante - o servidor pode estar rodando
            # mesmo sem conexão com Google Sheets
             # Verificação tolerante - servidor sempre está rodando
            env_ok = os.getenv('GOOGLE_SHEETS_CREDENTIALS') is not None
            sheets_ok = sheets_status.get('initialized', False)
            
            # Servidor está healthy se as variáveis estão configuradas,
            # mesmo que a conexão com Sheets não esteja ativa no momento
            status = 'healthy' if env_ok else 'degraded'
            #status = 'healthy' if (env_ok and sheets_ok) else 'degraded'
            
            return jsonify({
                'status': status,
                'timestamp': datetime.now().isoformat(),
                'details': {
                    'environment_configured': env_ok,
                    'sheets_connected': sheets_ok,
                    'last_test_time': sheets_status.get('last_test_time')
                }
            }), 200 # ✅ SEMPRE 200 #if status == 'healthy' else 503 ## Sempre retorna 200, o status indica a saúde
            
        except Exception as e:
            #'status': 'unhealthy',
            return jsonify({
                'status': 'degraded',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }), 200  # ✅ SEMPRE 200  # Mantém 200 para não quebrar o health check #500

# ... (mantenha as outras funções e rotas)

# ROTAS DE DEBUG E DIAGNÓSTICO
@app.route('/debug', methods=['GET'])
def debug_info():
    """Endpoint principal de debug com informações gerais"""
    with tracer.start_as_current_span("debug_info"):
        try:
            # Informações básicas do sistema
            system_info = {
                'app_name': 'Sheets App API',
                'version': '1.0.0',
                'environment': os.getenv('ENVIRONMENT', 'production'),
                'current_time': datetime.now().isoformat(),
                'python_version': os.sys.version,
                'status': sheets_status
            }
            
            return jsonify(system_info), 200
            
        except Exception as e:
            return jsonify({
                'error': f'Erro ao coletar informações de debug: {str(e)}'
            }), 500

@app.route('/debug/environment', methods=['GET'])
def debug_environment():
    """Endpoint para mostrar variáveis de ambiente (sem valores sensíveis)"""
    with tracer.start_as_current_span("debug_environment"):
        try:
            # Lista de variáveis sensíveis que não devem ser expostas
            sensitive_keys = [
                'GOOGLE_SHEETS_CREDENTIALS', 'CLOUDINARY_API_SECRET', 
                'API_KEY', 'SECRET_KEY', 'PASSWORD', 'TOKEN', 'PRIVATE_KEY'
            ]
            
            env_vars = {}
            for key, value in os.environ.items():
                # Ocultar valores de variáveis sensíveis
                if any(sensitive in key.upper() for sensitive in sensitive_keys):
                    env_vars[key] = '*** HIDDEN ***'
                else:
                    env_vars[key] = value
            
            return jsonify({
                'environment_variables': env_vars,
                'sensitive_keys_filtered': sensitive_keys
            }), 200
            
        except Exception as e:
            return jsonify({
                'error': f'Erro ao coletar variáveis de ambiente: {str(e)}'
            }), 500

@app.route('/debug/sheets', methods=['GET'])
def debug_sheets():
    """Endpoint para debug específico do Google Sheets"""
    with tracer.start_as_current_span("debug_sheets"):
        try:
            # Verificar variáveis de ambiente
            env_check = check_environment_variables()
            
            # Verificar credenciais
            creds_check = parse_credentials()
            
            # Testar conexão
            connection_test = None
            if env_check['all_found'] and creds_check['success']:
                try:
                    connection_test = test_google_sheets_connection()
                except Exception as conn_error:
                    connection_test = {'success': False, 'error': str(conn_error)}
            
            # Informações do cache
            cache_info = {
                'client_cached': _client_cache is not None,
                'spreadsheet_cached': _spreadsheet_cache is not None
            }
            
            return jsonify({
                'environment_check': env_check,
                'credentials_check': creds_check,
                'connection_test': connection_test,
                'cache_info': cache_info,
                'status': sheets_status,
                'timestamp': datetime.now().isoformat()
            }), 200
            
        except Exception as e:
            return jsonify({
                'error': f'Erro no debug do Sheets: {str(e)}'
            }), 500

@app.route('/debug/credentials', methods=['GET'])
def debug_credentials():
    """Endpoint para verificar status das credenciais"""
    with tracer.start_as_current_span("debug_credentials"):
        try:
            # Verificar se as credenciais estão presentes
            creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
            creds_present = creds_json is not None and len(creds_json.strip()) > 0
            
            # Verificar formato básico
            format_valid = False
            is_base64 = False
            project_id = None
            client_email = None
            
            if creds_present:
                try:
                    # Verificar se é base64
                    test_creds = creds_json.strip()
                    if test_creds.startswith('eyJ'):  # JWT normalmente começa com eyJ
                        try:
                            decoded = base64.b64decode(test_creds).decode('utf-8')
                            is_base64 = True
                            test_creds = decoded
                        except:
                            pass
                    
                    # Tentar fazer parse do JSON
                    creds_dict = json.loads(test_creds)
                    format_valid = True
                    
                    # Extrair informações não sensíveis
                    project_id = creds_dict.get('project_id')
                    client_email = creds_dict.get('client_email')
                    
                except (json.JSONDecodeError, UnicodeDecodeError):
                    format_valid = False
            
            # Verificar Cloudinary
            cloudinary_configured = all([
                os.getenv('CLOUDINARY_CLOUD_NAME'),
                os.getenv('CLOUDINARY_API_KEY'), 
                os.getenv('CLOUDINARY_API_SECRET')
            ])
            
            return jsonify({
                'google_sheets': {
                    'credentials_present': creds_present,
                    'format_valid': format_valid,
                    'is_base64_encoded': is_base64,
                    'project_id': project_id,
                    'client_email': client_email,
                    'status': sheets_status
                },
                'cloudinary': {
                    'configured': cloudinary_configured,
                    'cloud_name': bool(os.getenv('CLOUDINARY_CLOUD_NAME')),
                    'api_key': bool(os.getenv('CLOUDINARY_API_KEY')),
                    'api_secret': bool(os.getenv('CLOUDINARY_API_SECRET'))
                },
                'timestamp': datetime.now().isoformat()
            }), 200
            
        except Exception as e:
            return jsonify({
                'error': f'Erro ao verificar credenciais: {str(e)}'
            }), 500

@app.route('/debug/cloudinary', methods=['GET'])
def debug_cloudinary():
    """Endpoint para verificar configuração do Cloudinary"""
    with tracer.start_as_current_span("debug_cloudinary"):
        try:
            # Verificar configuração básica
            config_status = {
                'cloud_name': bool(os.getenv('CLOUDINARY_CLOUD_NAME')),
                'api_key': bool(os.getenv('CLOUDINARY_API_KEY')),
                'api_secret': bool(os.getenv('CLOUDINARY_API_SECRET')),
                'fully_configured': all([
                    os.getenv('CLOUDINARY_CLOUD_NAME'),
                    os.getenv('CLOUDINARY_API_KEY'),
                    os.getenv('CLOUDINARY_API_SECRET')
                ])
            }
            
            # Testar conexão simples (sem fazer upload real)
            test_result = None
            if config_status['fully_configured']:
                try:
                    # Teste simples da API
                    result = cloudinary.api.ping()
                    test_result = {
                        'status': result.get('status') if result else 'unknown',
                        'success': result is not None
                    }
                except Exception as e:
                    test_result = {
                        'success': False,
                        'error': str(e)
                    }
            
            return jsonify({
                'configuration': config_status,
                'connection_test': test_result,
                'timestamp': datetime.now().isoformat()
            }), 200
            
        except Exception as e:
            return jsonify({
                'error': f'Erro ao verificar Cloudinary: {str(e)}'
            }), 500

# Problema: O frontend tenta acessar /metrics mas essa rota não está definida.
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import Counter, Histogram, Gauge

# Adicionar métricas Prometheus (se quiser monitoramento mais avançado)
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP Requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency', ['endpoint'])
ACTIVE_UPLOADS = Gauge('active_uploads', 'Active file uploads')

@app.route('/metrics', methods=['GET'])
def metrics():
    """Endpoint para métricas Prometheus"""
    try:
        return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}
    except Exception as e:
        return jsonify({'error': f'Erro ao gerar métricas: {str(e)}'}), 500



#3. Problema na Inicialização do Servidor
#16.09.2025, 18:46 3. Atualize a rota /debug/full:
@app.route('/debug/full', methods=['GET'])
def debug_full():
    """Endpoint completo de debug que combina todas as informações"""
    with tracer.start_as_current_span("debug_full"):
        try:
            """
            # Coletar informações de todas as rotas de debug
            sheets_info = debug_sheets().get_json()
            cloudinary_info = debug_cloudinary().get_json()
            credentials_info = debug_credentials().get_json()
            environment_info = debug_environment().get_json()
            """
            
            # Chame as funções internas diretamente em vez das rotas
            sheets_info = debug_sheets_internal()
            cloudinary_info = debug_cloudinary_internal()
            credentials_info = debug_credentials_internal()
            environment_info = debug_environment_internal()
            
            # Calcular tempo de resposta
            start_time = datetime.now()
            
            # Testar conexão com Sheets se possível
            sheets_connection = None
            env_check = sheets_info.get('environment_check', {})
            
            if env_check and env_check.get('all_found', False):
                try:
                    sheets_connection = test_google_sheets_connection()
                except Exception as e:
                    sheets_connection = {'success': False, 'error': str(e)}
                    
            """ 
            if sheets_info.get('environment_check', {}).get('all_found', False):
                try:
                    sheets_connection = test_google_sheets_connection()
                except Exception as e:
                    sheets_connection = {'success': False, 'error': str(e)}
            """
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            return jsonify({
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'duration_seconds': duration,
                'sheets': sheets_info,
                'cloudinary': cloudinary_info,
                'credentials': credentials_info,
                'environment': environment_info,
                'sheets_connection_test': sheets_connection,
                'status': {
                    'sheets_configured': env_check.get('all_found', False) if env_check else False,
                    'cloudinary_configured': cloudinary_info.get('configuration', {}).get('fully_configured', False),
                    'sheets_connected': sheets_connection.get('success', False) if sheets_connection else False
                }
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Erro no debug completo: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }), 500
            
@app.route('/debug/simple', methods=['GET'])
def debug_simple():
    """Endpoint simples de debug"""
    return jsonify({
        'status': 'ok',
        'message': 'Servidor está funcionando',
        'timestamp': datetime.now().isoformat(),
        'sheets_configured': os.getenv('GOOGLE_SHEETS_CREDENTIALS') is not None,
        'cloudinary_configured': all([
            os.getenv('CLOUDINARY_CLOUD_NAME'),
            os.getenv('CLOUDINARY_API_KEY'),
            os.getenv('CLOUDINARY_API_SECRET')
        ])
    })

# 16.09, 18:51 4. Adicione a rota /api/sheets/data que o frontend também precisa:
@app.route('/api/sheets/data', methods=['GET'])
def get_sheets_data():
    """Endpoint para obter dados da planilha"""
    with tracer.start_as_current_span("get_sheets_data"):
        try:
            worksheet_name = request.args.get('worksheet', 'Imagens')
            
            if not sheets_status['initialized']:
                # Tenta reconectar se não estiver inicializado
                try:
                    test_google_sheets_connection()
                except:
                    pass
            
            client, spreadsheet = get_sheets_client()
            worksheet = spreadsheet.worksheet(worksheet_name)
            
            # Obter todos os dados da worksheet
            data = worksheet.get_all_records()
            
            # Obter metadados
            metadata = {
                'total_rows': len(data),
                'total_columns': len(data[0]) if data else 0,
                'worksheet': worksheet_name,
                'last_update': datetime.now().isoformat()
            }
            
            return jsonify({
                'success': True,
                'data': data,
                'metadata': metadata
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Erro ao obter dados: {str(e)}'
            }), 500

# 17.09 10:19, 3. Verificação da configuração atual do servidor
@app.route('/debug/cors-test', methods=['GET', 'OPTIONS'])
def debug_cors_test():
    """Endpoint para testar configuração CORS"""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'preflight ok'})
        response.headers.add('Access-Control-Allow-Origin', 'https://stick35em10.github.io')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,OPTIONS')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response
    
    return jsonify({
        'message': 'CORS test successful',
        'origin': request.headers.get('Origin'),
        'timestamp': datetime.now().isoformat()
    })

# 18.09.2025, 16:10, 2. Modifique a rota /api/sheets/add-data para incluir o cálculo do saldo: 
@app.route('/api/sheets/add-data', methods=['POST', 'OPTIONS'])
def add_data_to_sheet():
    """Endpoint para adicionar dados à planilha"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    with tracer.start_as_current_span("add_data_to_sheet") as span:
        try:
            if not sheets_status['initialized']:
                sheets_result = test_google_sheets_connection()
                if not sheets_result.get('success', False):
                    return jsonify({
                        'success': False,
                        'error': 'Erro de autenticação com o Google Sheets'
                    }), 500
            
            # Obter dados do JSON
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'error': 'Nenhum dado fornecido'
                }), 400
            
            worksheet_name = data.get('worksheet', 'estoque')#'Fluxo de Caixa') #'Dados')
            row_data = data.get('data', {})#[])
            
            span.set_attribute("worksheet", worksheet_name)
            client, spreadsheet = get_sheets_client()
            
            # Verificar se a worksheet existe, se não, criar
            try:
                worksheet = spreadsheet.worksheet(worksheet_name)
            except gspread.exceptions.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows="1000", cols="10")
                
                # Adicionar cabeçalhos padrão para fluxo de caixa
                headers = [
                    "Data", "Tipo",	"Quantidade", "Fornecedor/Revendedor", 
                    "Nº Da Factura",	"Saldo Atual",	"Observações"
                ]
                worksheet.append_row(headers)
                log_step("ADD_DATA", f"✅ Nova worksheet criada: {worksheet_name}")
            
            # CALCULAR SALDO
            saldo_anterior = calculate_current_balance(spreadsheet, worksheet_name)
            
            # Extrair valores de entrada e saída
            #entrada = float(row_data.get('Entrada', 0) or 0)
            #saida = float(row_data.get('Saída', 0) or 0)
            #saldo_atual = saldo_anterior + entrada - saida
            
            # Extrair valores de quantidade
            quantidade = float(row_data.get('Quantidade', 0) or 0)
            tipo = row_data.get('Tipo', '')
            
            # Calcular novo saldo baseado no tipo (Entrada/Saída)
            if tipo.lower() == 'entrada':
                saldo_atual = saldo_anterior + quantidade
            elif tipo.lower() == 'saída':
                saldo_atual = saldo_anterior - quantidade
            else:
                saldo_atual = saldo_anterior  # Se tipo não especificado, mantém o saldo
                
            # Preparar dados completos para a linha
            complete_row_data = {
                "Data": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "Fornecedor/Revendedor": row_data.get('Fornecedor/Revendedor', ''),
                "Nº Da Factura": row_data.get('Nº Da Factura', ''),
                "Observações": row_data.get('Observações', ''),
                "Quantidade": quantidade,
                "Saldo Atual": saldo_atual,
                "Tipo": tipo
                #"Descrição": row_data.get('Descrição', ''),
                #"Categoria": row_data.get('Categoria', ''),
                #"Entrada": entrada,
                #"Saída": saida,
                #"Saldo Anterior": saldo_anterior,
                #"Saldo Atual": saldo_atual,
                #"Tipo": row_data.get('Tipo', ''),
                #"Observações": row_data.get('Observações', '')
            }
            
            # Obter cabeçalhos existentes
            headers = worksheet.row_values(1)
            if not headers:
                headers = list(complete_row_data.keys())
                worksheet.append_row(headers)
            
            # Criar linha na ordem dos cabeçalhos
            row_values = []
            for header in headers:
                row_values.append(complete_row_data.get(header, ''))
            
            # Adicionar à planilha
            worksheet.append_row(row_values)
            
            log_step("ADD_DATA", f"✅ Dados adicionados com saldo: {saldo_atual}") # R$ {saldo_atual:.2f}")
            
            return jsonify({
                'success': True,
                'message': 'Dados adicionados com sucesso',
                'worksheet': worksheet_name,
                'saldo_anterior': saldo_anterior,
                'saldo_atual': saldo_atual,
                'spreadsheet_title': spreadsheet.title
            }), 200
            
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            error_msg = f"Erro ao adicionar dados: {str(e)}"
            log_step("ADD_DATA", error_msg, False)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
            """
            if not row_data:
                return jsonify({
                    'success': False,
                    'error': 'Nenhum dado para adicionar'
                }), 400
            
            span.set_attribute("worksheet", worksheet_name)
            span.set_attribute("data_length", len(row_data))
            
            client, spreadsheet = get_sheets_client()
            
            # Verificar se a worksheet existe, se não, criar
            try:
                worksheet = spreadsheet.worksheet(worksheet_name)
            except gspread.exceptions.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows="1000", cols="20")
                log_step("ADD_DATA", f"✅ Nova worksheet criada: {worksheet_name}")
            
            # Adicionar timestamp se não estiver presente
            if isinstance(row_data, list):
                # Se for uma lista de valores, adicionar timestamp no início
                row_data = [datetime.now().strftime('%Y-%m-%d %H:%M:%S')] + row_data
            elif isinstance(row_data, dict):
                # Se for um dicionário, adicionar campo de timestamp
                row_data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Adicionar à planilha
            if isinstance(row_data, list):
                worksheet.append_row(row_data)
            else:
                # Para dicionários, precisamos obter os cabeçalhos primeiro
                headers = worksheet.row_values(1)
                if not headers:
                    # Se não houver cabeçalhos, criar com as chaves do dicionário
                    headers = list(row_data.keys())
                    worksheet.append_row(headers)
                
                # Criar linha na ordem dos cabeçalhos
                row_values = []
                for header in headers:
                    row_values.append(row_data.get(header, ''))
                
                worksheet.append_row(row_values)
            
            log_step("ADD_DATA", f"✅ Dados adicionados à worksheet '{worksheet_name}'")
            
            return jsonify({
                'success': True,
                'message': 'Dados adicionados com sucesso',
                'worksheet': worksheet_name,
                'spreadsheet_title': spreadsheet.title
            }), 200
            
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            error_msg = f"Erro ao adicionar dados: {str(e)}"
            log_step("ADD_DATA", error_msg, False)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
            
            """

# 18.09 16:22, 3. Adicione uma rota para obter o saldo atual:
@app.route('/api/sheets/balance', methods=['GET'])
def get_current_balance():
    """Endpoint para obter o saldo atual"""
    with tracer.start_as_current_span("get_current_balance"):
        try:
            worksheet_name = request.args.get('worksheet', 'Fluxo de Caixa')
            
            if not sheets_status['initialized']:
                try:
                    test_google_sheets_connection()
                except:
                    pass
            
            client, spreadsheet = get_sheets_client()
            
            saldo_atual = calculate_current_balance(spreadsheet, worksheet_name)
            
            return jsonify({
                'success': True,
                'worksheet': worksheet_name,
                'saldo_atual': saldo_atual,
                'timestamp': datetime.now().isoformat()
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Erro ao obter saldo: {str(e)}'
            }), 500

# [19,18].09 [[07:31,],16:24], 4. Adicione uma rota para recálculo completo do saldo:
@app.route('/api/sheets/recalculate-balance', methods=['POST'])
def recalculate_balance():
    """Recalcula todos os saldos da planilha"""
    with tracer.start_as_current_span("recalculate_balance"):
        try:
            worksheet_name = request.args.get('worksheet', 'estoque') #'Fluxo de Caixa')
            
            if not sheets_status['initialized']:
                return jsonify({
                    'success': False,
                    'error': 'Google Sheets não inicializado'
                }), 500
            
            client, spreadsheet = get_sheets_client()
            worksheet = spreadsheet.worksheet(worksheet_name)
            
            
            # Obter cabeçalhos para encontrar a posição correta das colunas
            headers = worksheet.row_values(1)
            
            # Encontrar índices das colunas
            quantidade_col = headers.index('Quantidade') + 1 if 'Quantidade' in headers else 4
            tipo_col = headers.index('Tipo') + 1 if 'Tipo' in headers else 2
            saldo_col = headers.index('Saldo Atual') + 1 if 'Saldo Atual' in headers else 6
            
            records = worksheet.get_all_records()
            if not records:
                return jsonify({
                    'success': True,
                    'message': 'Nenhum dado para recalcular'
                }), 200
            
            # Recalcular todos os saldos
            saldo_atual = 0.0
            updated_count = 0
            
            for i, record in enumerate(records, start=2):  # start=2 porque a linha 1 são cabeçalhos
                #entrada = float(record.get('Entrada', 0) or 0)
                #saida = float(record.get('Saída', 0) or 0)
                
                quantidade = float(record.get('Quantidade', 0) or 0)
                tipo = record.get('Tipo', '').lower()
                
                # Calcular baseado no tipo
                if tipo == 'entrada':
                    saldo_atual += quantidade
                elif tipo == 'saída':
                    saldo_atual -= quantidade
                    
                # Atualizar saldo anterior (saldo da linha anterior)
                #worksheet.update_cell(i, 6, saldo_atual)  # Coluna 6 = Saldo Atual #Saldo Anterior
                worksheet.update_cell(i, saldo_col, saldo_atual)
                updated_count += 1
                
                """
                # Calcular novo saldo atual
                novo_saldo = saldo_atual + entrada - saida
                worksheet.update_cell(i, 7, novo_saldo)  # Coluna 7 = Saldo Atual
                
                saldo_atual = novo_saldo
                updated_count += 1
                """
            return jsonify({
                'success': True,
                'message': f'Recalculado {updated_count} registros',
                'novo_saldo': saldo_atual,
                'worksheet': worksheet_name
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Erro ao recalcular saldos: {str(e)}'
            }), 500 

if __name__ == '__main__':
    # Inicialização automática ao iniciar o servidor
    with tracer.start_as_current_span("app_startup"):
        log_step("APP_STARTUP", "🚀 Iniciando Sheets App API...")
        
        # Verificar ambiente mas não falhar se houver problemas
        try:
            # Verificar ambiente
            env_check = check_environment_variables()
            
            if env_check['all_found']:
                log_step("APP_STARTUP", "✅ Todas as variáveis de ambiente encontradas")
                
                # Testar conexão em background MAS não falhar se der erro
                try:
                    test_result = test_google_sheets_connection()
                    if test_result['success']:
                        log_step("APP_STARTUP", "🎉 Conexão com Google Sheets estabelecida com sucesso!")
                    else:
                        log_step("APP_STARTUP", f"⚠️ Conexão falhou: {test_result.get('error', 'Erro desconhecido')}", False)
                        # Não marcar como falha completa - servidor ainda pode funcionar
                        sheets_status['initialized'] = False
                except Exception as e:
                    log_step("APP_STARTUP", f"⚠️ Erro durante inicialização: {str(e)}", False)
                    sheets_status['initialized'] = False
            else:
                log_step("APP_STARTUP", f"❌ Variáveis ausentes: {env_check['missing_vars']}", False)
                sheets_status['initialized'] = False
                
        except Exception as e:
            log_step("APP_STARTUP", f"⚠️ Erro durante inicialização: {str(e)}", False)    
            
        # Iniciar servidor MESMO sem conexão com Sheets
        port = int(os.environ.get('PORT', 5000))
        log_step("APP_STARTUP", f"🌐 Servidor iniciado na porta {port}")
        
        app.run(host='0.0.0.0', port=port, debug=False)