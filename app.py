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

SHARED_DRIVE_ID = '1T3bLqnSCLg3_zkqnj5JXzH8tvN-h63yy'

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

# ROTAS DE API
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

### Para incluir o monitoramento OpenTelemetry no servidor Flask e visualizar as métricas no HTML, você precisa fazer várias modificações.

# Adicione estas importações no início do arquivo
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.metrics import set_meter_provider

# Modifique a função init_opentelemetry para incluir métricas
def init_opentelemetry():
    """Initialize OpenTelemetry tracing, metrics and logging"""
    try:
        # Set up tracing
        resource = Resource.create({
            "service.name": "sheets-app-api",
            "service.version": "1.0.0",
            "deployment.environment": os.getenv("ENVIRONMENT", "production")
        })
        
        # Tracing
        trace.set_tracer_provider(TracerProvider(resource=resource))
        
        otlp_trace_exporter = OTLPSpanExporter(
            endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces"),
        )
        
        span_processor = BatchSpanProcessor(otlp_trace_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)
        
        # Metrics
        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(
                endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/metrics"),
            ),
            export_interval_millis=5000
        )
        
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[metric_reader]
        )
        set_meter_provider(meter_provider)
        
        # Logging
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

# Adicione estas métricas após as importações
from opentelemetry.metrics import get_meter

# Obter meter para métricas
meter = get_meter(__name__)

# Criar métricas
REQUEST_COUNTER = meter.create_counter(
    "http_requests_total",
    description="Total HTTP requests",
    unit="1"
)

REQUEST_DURATION = meter.create_histogram(
    "http_request_duration_seconds",
    description="HTTP request duration in seconds",
    unit="s"
)

ACTIVE_REQUESTS = meter.create_up_down_counter(
    "http_requests_active",
    description="Active HTTP requests",
    unit="1"
)

# Adicione um middleware para rastrear todas as requisições
@app.before_request
def before_request():
    request.start_time = time.time()
    ACTIVE_REQUESTS.add(1, {"method": request.method, "endpoint": request.path})

@app.after_request
def after_request(response):
    duration = time.time() - request.start_time
    REQUEST_COUNTER.add(1, {
        "method": request.method, 
        "endpoint": request.path,
        "status_code": str(response.status_code)
    })
    REQUEST_DURATION.record(duration, {
        "method": request.method,
        "endpoint": request.path,
        "status_code": str(response.status_code)
    })
    ACTIVE_REQUESTS.add(-1, {"method": request.method, "endpoint": request.path})
    return response

# Adicione uma rota para obter métricas do OpenTelemetry
@app.route('/otel/metrics', methods=['GET'])
def get_otel_metrics():
    """Endpoint para obter métricas do OpenTelemetry"""
    with tracer.start_as_current_span("get_otel_metrics"):
        try:
            # Coletar métricas básicas do sistema
            import psutil
            process = psutil.Process()
            
            metrics_data = {
                'system': {
                    'cpu_percent': psutil.cpu_percent(),
                    'memory_percent': psutil.virtual_memory().percent,
                    'process_memory_mb': process.memory_info().rss / 1024 / 1024,
                    'process_cpu_percent': process.cpu_percent()
                },
                'requests': {
                    'total_requests': REQUEST_COUNTER,
                    'active_requests': ACTIVE_REQUESTS
                },
                'otel_status': {
                    'tracing_initialized': trace.get_tracer_provider() is not None,
                    'metrics_initialized': get_meter_provider() is not None,
                    'logging_initialized': get_logger_provider() is not None
                }
            }
            
            return jsonify(metrics_data), 200
            
        except Exception as e:
            return jsonify({'error': f'Erro ao coletar métricas: {str(e)}'}), 500
        

#3. Problema na Inicialização do Servidor

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