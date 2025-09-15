// Configuração fixa do servidor
const SERVER_URL = "https://visualizing-geospatial-data-in-python-4.onrender.com";
const WORKSHEET_NAME = "Images";

// Estado da aplicação
let isConnected = false;
let allData = [];
let selectedFiles = [];
let capturedPhotos = [];
let currentLocation = null;
let cameraLocation = null;
let stream = null;
let otelConnected = false;
let imageData = [];
let metricsInterval = null;
let autoMetricsEnabled = false;
let cpuChart = null;
let memoryChart = null;
const metricHistory = {
    cpu: [],
    memory: [],
    timestamps: []
};

// Elementos do DOM
const btnTest = document.getElementById('btnTest');
const btnLoad = document.getElementById('btnLoad');
const btnRefresh = document.getElementById('btnRefresh');
const statusEl = document.getElementById('status');
const otelStatus = document.getElementById('otelStatus');
const tabs = document.querySelectorAll('.tab');
const tabContents = document.querySelectorAll('.tab-content');
const searchInput = document.getElementById('search');
const entriesSelect = document.getElementById('entries');
const dataContainer = document.getElementById('data');
const dataStats = document.getElementById('dataStats');
const uploadForm = document.getElementById('uploadForm');
const photoFiles = document.getElementById('photoFiles');
const btnLocation = document.getElementById('btnLocation');
const locationStatus = document.getElementById('locationStatus');
const filePreview = document.getElementById('filePreview');
const submitUpload = document.getElementById('submitUpload');
const uploadResults = document.getElementById('uploadResults');
const uploadResultsContent = document.getElementById('uploadResultsContent');
const videoElement = document.getElementById('videoElement');
const captureBtn = document.getElementById('captureBtn');
const clearPhotosBtn = document.getElementById('clearPhotosBtn');
const btnCameraLocation = document.getElementById('btnCameraLocation');
const cameraLocationStatus = document.getElementById('cameraLocationStatus');
const cameraPreview = document.getElementById('cameraPreview');
const submitCamera = document.getElementById('submitCamera');
const modal = document.getElementById('imageModal');
const modalImage = document.getElementById('modalImage');
const modalClose = document.querySelector('.modal-close');
const btnHealthCheck = document.getElementById('btnHealthCheck');
const healthStatus = document.getElementById('healthStatus');
const btnEnvCheck = document.getElementById('btnEnvCheck');
const btnCredsCheck = document.getElementById('btnCredsCheck');
const btnCloudinaryCheck = document.getElementById('btnCloudinaryCheck');
const btnMetrics = document.getElementById('btnMetrics');
const monitoringResults = document.getElementById('monitoringResults');
const monitoringData = document.getElementById('monitoringData');
const btnOtelMetrics = document.getElementById('btnOtelMetrics');
const btnSystemMetrics = document.getElementById('btnSystemMetrics');
const btnAutoMetrics = document.getElementById('btnAutoMetrics');
const otelMetricsResults = document.getElementById('otelMetricsResults');
const otelMetricsData = document.getElementById('otelMetricsData');

// Funções para monitoramento OpenTelemetry
async function getOtelMetrics() {
    showMonitoringResults('Buscando métricas OpenTelemetry...');
    try {
        const result = await makeRequest('/otel/metrics');
        showOtelMetricsResults(result);
    } catch (error) {
        showMonitoringResults(`Erro: ${error.message}`);
    }
}

async function getSystemMetrics() {
    showMonitoringResults('Buscando métricas do sistema...');
    try {
        // Você pode adicionar endpoints específicos para métricas do sistema
        const healthResult = await makeRequest('/health');
        const sheetsResult = await makeRequest('/debug/sheets');
        
        const systemMetrics = {
            health: healthResult,
            sheets: sheetsResult,
            timestamp: new Date().toISOString()
        };
        
        showOtelMetricsResults(systemMetrics);
    } catch (error) {
        showMonitoringResults(`Erro: ${error.message}`);
    }
}

function showOtelMetricsResults(data) {
      otelMetricsResults.style.display = 'block';
      
      if (data.system) {
          // Formatar métricas do sistema
          otelMetricsData.innerHTML = `
              <div style="margin-bottom: 15px;">
                  <h5>🖥️ Sistema</h5>
                  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                      <div>CPU: <strong>${data.system.cpu_percent}%</strong></div>
                      <div>Memória: <strong>${data.system.memory_percent}%</strong></div>
                      <div>Memória Processo: <strong>${data.system.process_memory_mb.toFixed(2)} MB</strong></div>
                      <div>CPU Processo: <strong>${data.system.process_cpu_percent}%</strong></div>
                  </div>
              </div>
              
              <div style="margin-bottom: 15px;">
                  <h5>📊 OpenTelemetry Status</h5>
                  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                      <div>Tracing: <span style="color: ${data.otel_status.tracing_initialized ? '#4ade80' : '#f87171'}">${data.otel_status.tracing_initialized ? '✅' : '❌'}</span></div>
                      <div>Metrics: <span style="color: ${data.otel_status.metrics_initialized ? '#4ade80' : '#f87171'}">${data.otel_status.metrics_initialized ? '✅' : '❌'}</span></div>
                      <div>Logging: <span style="color: ${data.otel_status.logging_initialized ? '#4ade80' : '#f87171'}">${data.otel_status.logging_initialized ? '✅' : '❌'}</span></div>
                  </div>
              </div>
              
              <div>
                  <h5>🕒 Última Atualização</h5>
                  <div>${new Date().toLocaleString()}</div>
              </div>
          `;
      } else {
          // Dados genéricos
          otelMetricsData.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
      }
  }

// Funções utilitárias
function showMessage(html, kind='info', timeout=0){
  statusEl.className = 'status ' + (kind==='error'?'error':kind==='success'?'success':kind==='warning'?'warn':'');
  statusEl.innerHTML = html;
  if(timeout>0){ 
    setTimeout(()=>{ 
      statusEl.className='status'; 
      statusEl.innerHTML=''; 
    }, timeout); 
  }
}

function showLoading(msg){ showMessage(`⏳ ${msg}`, 'warn'); }

function resetConnection(){
  isConnected = false;
  btnLoad.disabled = true;
  btnRefresh.style.display = 'none';
  dataContainer.innerHTML = '';
}

function updateOtelStatus(connected) {
  otelConnected = connected;
  if (connected) {
    otelStatus.className = 'opentelemetry-status connected';
    otelStatus.innerHTML = '<span>📊 OpenTelemetry: Conectado</span>';
  } else {
    otelStatus.className = 'opentelemetry-status disconnected';
    otelStatus.innerHTML = '<span>📊 OpenTelemetry: Desconectado</span>';
  }
}

// Requisições para o servidor
async function makeRequest(path, options={}){
  const url = SERVER_URL.replace(/\/$/, '') + path;
  try {
    const res = await fetch(url, { 
      mode: 'cors',
      credentials: 'omit',
      headers: {
        'Accept': 'application/json',
        'Content-Type': options.body instanceof FormData ? undefined : 'application/json'
      },
      ...options
    });
    
    if(!res.ok){
      const txt = await res.text().catch(()=>'Network error');
      throw new Error(`HTTP ${res.status}: ${txt}`);
    }
    return res.json();
  } catch (error) {
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      throw new Error(`Conexão falhou. Verifique se o servidor está rodando.`);
    }
    throw error;
  }
}

// Testar conexão
// Modificar a função testConnection para lidar melhor com 503
async function testConnection(){
  showLoading('Testando conexão...');
  btnTest.disabled = true;
  
  try{
    // Teste básico de saúde primeiro
    const healthResult = await makeRequest('/health');
    
    let message = '';
    let success = false;
    
    // Modificar esta lógica para aceitar status 'degraded'
    if (healthResult.status === 'healthy' || healthResult.status === 'degraded') {
      // Servidor saudável, testar outras funcionalidades
      // Servidor está rodando (healthy ou degraded)
      try {
        const sheetsResult = await makeRequest('/debug/sheets');
        const cloudResult = await makeRequest('/debug/cloudinary');

        const envResult = await makeRequest('/debug/environment');
        const credsResult = await makeRequest('/debug/credentials');
        
        success = true; // Considera sucesso mesmo se Sheets falhar // sheetsResult && sheetsResult.success;
        message = `
          ✅ <strong>Serviço Online!</strong><br>
          📊 Google Sheets: ${sheetsResult && sheetsResult.success ? '✅ Conectado' : '❌ Desconectado'}<br>
          ☁️ Cloudinary: ${cloudResult.configuration.fully_configured ? '✅ Configurado' : '❌ Não configurado'}<br>
          Status: ${healthResult.status}
        `;
        
      } catch (sheetsError) {
        // Ainda mostra sucesso mas com aviso
        success = true;
        message = `
          ⚠️ <strong>Servidor online mas com problemas</strong><br>
          Status: ${healthResult.status}<br>
          Google Sheets: ❌ Desconectado<br>
          Erro no Google Sheets: ${sheetsError.message}
        `;
      }
    } else {
      // Servidor com problemas
      message = `
        ❌ <strong>Servidor com problemas</strong><br>
        Status: ${healthResult.status}<br>
        Detalhes: ${JSON.stringify(healthResult.details)}
      `;
    }
    
    showMessage(message, success ? 'success' : 'error');
    updateOtelStatus(healthResult.status === 'healthy');
    
    isConnected = success;
    btnLoad.disabled = !success;
    if (success) {
      btnRefresh.style.display = 'inline-block';
    }

  } catch(err) {
    console.error('Erro completo:', err);
    
    let errorMessage = `❌ Falha na conexão: ${err.message}`;
    
    if (err.message.includes('503')) {
      // Tratar 503 como "servidor rodando mas com problemas"
      errorMessage = `
        ⚠️ <strong>Servidor em modo degradado</strong><br>
        O servidor está rodando mas alguns serviços podem não estar disponíveis.<br>
        Detalhes: ${err.message}
      `;
      // Ainda permite carregar dados básicos
      isConnected = true;
      btnLoad.disabled = false;
      btnRefresh.style.display = 'inline-block';
    } else if (err.message.includes('Failed to fetch')) {
      errorMessage = '❌ Não foi possível conectar ao servidor. Verifique si está online.';
    }
    
    //showMessage(errorMessage, 'error');
    showMessage(errorMessage, err.message.includes('503') ? 'warn' : 'error');

    //resetConnection();
    //updateOtelStatus(false);
    if (!err.message.includes('503')) {
      resetConnection();
    }
    updateOtelStatus(false);
  } finally {
    btnTest.disabled = false;
  }
}

// Carregar dados do servidor
async function loadData() {
  showLoading('Carregando dados...');
  
  try {
    const response = await fetch(`${SERVER_URL}/images`);
    if (response.ok) {
      imageData = await response.json();
      console.log('Dados recebidos:', imageData); // DEBUG
      
      // DEBUG: Verificar estrutura
      debugDataStructure(imageData);

      // 15.09 11:22, Processar URLs para garantir que são válidas
      imageData = imageData.map(item => {
        // 15.09 13:57, USAR O CAMPO CORRETO: 'url_link' para a URL da imagem // USAR O CAMPO CORRETO: 'URL da Imagem' em vez de 'url_link'
        const imageUrl = item.url || item.url_link || item.file_path ||  item['URL da Imagem'] || ''; //item['URL da Imagem'] || item.url || item.file_path;
        
        return {
          ...item,
          url: ensureValidUrl(imageUrl), //(item.url),
          file_path: ensureValidUrl(imageUrl), //item.file_path),
          thumbnail_path: ensureValidUrl(imageUrl) //item.thumbnail_path)
        }; // return {
      });

      // 15.09 13:31 Dentro da função loadData(), após imageData = await response.json();
      debugDataFields(imageData);

      displayData(imageData);
      showMessage(`✅ Dados carregados: ${imageData.length} imagens encontradas`, 'success');

      // Debug: verificar estrutura dos dados
      if (imageData.length > 0) {
        console.log('Primeiro item:', imageData[0]);
        console.log('Campos disponíveis:', Object.keys(imageData[0]));
      }

    } else {
      throw new Error(`Status: ${response.status}`);
    }
  } catch (error) {
    showMessage(`❌ Falha ao carregar dados: ${error.message}`, 'error');

    // Tentar debug para entender a estrutura
    try {
      const debugResponse = await fetch(`${SERVER_URL}/debug/images`);
      if (debugResponse.ok) {
        const debugData = await debugResponse.json();
        console.log('Estrutura dos dados (debug):', debugData);
        console.log('Cabeçalhos da planilha:', debugData.headers);
      }
    } catch (debugError) {
      console.error('Erro no debug:', debugError);
    }

    // Carregar dados de fallback para teste
    loadFallbackData();
  } // catch (error) {

} // async function loadData() {

// Dados de fallback para teste
function loadFallbackData() {
    imageData = [
      {
        'Data': '2024-09-15 10:30:00',
        'Título': 'Foto de Teste',
        'Descrição': 'Esta é uma foto de teste para demonstração',
        'Nome do Arquivo Original': 'imagem_teste.jpg',
        'url_link': 'https://res.cloudinary.com/demo/image/upload/sample.jpg',
        'Latitude': -23.5505,
        'Longitude': -46.6333,
        'URL da Imagem': 'https://res.cloudinary.com/demo/image/upload/sample.jpg'
      },
      {
        'Data': '2024-09-15 11:45:00',
        'Título': 'Outra Foto',
        'Descrição': 'Segunda imagem de teste',
        'Nome do Arquivo Original': 'outra_imagem.jpg',
        'url_link': 'https://picsum.photos/400/300',
        'Latitude': -23.5510,
        'Longitude': -46.6340,
        'URL da Imagem': 'https://picsum.photos/400/300'
      }
    ];
    
    displayData(imageData);
    showMessage('⚠️ Usando dados de demonstração (servidor offline)', 'warn');
}

// Função para debug da estrutura dos dados
function debugDataStructure(data) {
  console.log('=== DEBUG DA ESTRUTURA DOS DADOS ===');
  console.log('Tipo:', Array.isArray(data) ? 'Array' : typeof data);
  console.log('Quantidade:', Array.isArray(data) ? data.length : 'N/A');
  
  if (Array.isArray(data) && data.length > 0) {
    console.log('Primeiro item:', data[0]);
    console.log('Campos do primeiro item:', Object.keys(data[0]));
    
    // Verificar campos de URL
    const firstItem = data[0];
    const urlFields = Object.keys(firstItem).filter(key => 
      key.toLowerCase().includes('url') || 
      key.toLowerCase().includes('link') ||
      key.toLowerCase().includes('path')
    );
    
    console.log('Campos possíveis para URL:', urlFields);
    
    // Verificar valores dos campos de URL
    urlFields.forEach(field => {
      console.log(`${field}:`, firstItem[field]);
    });
  }
}

// Função para debug dos campos disponíveis
function debugDataFields(data) {
  if (data.length > 0) {
    console.log('=== CAMPOS DISPONÍVEIS ===');
    const fields = Object.keys(data[0]);
    console.log('Total de campos:', fields.length);
    console.log('Lista de campos:', fields);
    
    // Campos que podem conter URLs
    const urlFields = fields.filter(f => 
      f.toLowerCase().includes('url') || 
      f.toLowerCase().includes('link') ||
      f.toLowerCase().includes('path')
    );
    console.log('Campos de URL:', urlFields);
    
    // Verificar valores de exemplo
    urlFields.forEach(field => {
      console.log(`Valor de exemplo para "${field}":`, data[0][field]);
    });
  }
}

// Função para garantir URL válida
function ensureValidUrl(url) {
  if (!url) return '';
  
  // Se já é uma URL completa
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return url;
  }
  
  // Se é um caminho Cloudinary ou outro provedor
  if (url.includes('cloudinary') || url.includes('res.cloudinary.com')) {
    return `https://${url.replace(/^\/\//, '')}`;
  }
  
  // Se é um caminho relativo, assumir que é do Cloudinary
  if (url.startsWith('v')) { // Padrão Cloudinary: v1234567/...
    return `https://res.cloudinary.com/demo/image/upload/${url}`;
  }
  
  return url;
}

// Exibir dados na tabela
function displayData(data) {
  if (!data || data.length === 0) {
    dataContainer.innerHTML = '<p>Nenhum dado encontrado.</p>';
    dataStats.innerHTML = '';
    return;
  }

  // Estatísticas
  const statsHtml = `
    <div class="stats">
      <strong>📊 Estatísticas:</strong> 
      ${data.length} imagens carregadas | 
      ${data.filter(item => item.Latitude && item.Longitude).length} com geolocalização
    </div>
  `;
  dataStats.innerHTML = statsHtml;

  // Criar tabela
  let tableHtml = `
    <table class="data-table">
      <thead>
        <tr>
          <th>Miniatura</th>
          <th>Título</th>
          <th>Descrição</th>
          <th>Data</th>
          <th>Localização</th>
          <th>Ações</th>
        </tr>
      </thead>
      <tbody>
  `;

  data.forEach((item, index) => {
    // 15.09 13:57, USAR O CAMPO CORRETO: 'url_link' para a URL da imagem // USAR O CAMPO CORRETO: 'URL da Imagem' em vez de 'url_link'
    const imageUrl = item.url || item.url_link || item.file_path || item['URL da Imagem'] || '';
    const title = item.Título || item.title || 'Sem título';
    const description = item.Descrição || item.description || '';
    const date = item.Data || item.date || '';
    const lat = item.Latitude || item.latitude;
    const lng = item.Longitude || item.longitude;
    
    const location = (lat && lng) ? 
      `${lat.toFixed(4)}, ${lng.toFixed(4)}` : 'Não disponível';

    tableHtml += `
      <tr>
        <td>
          ${imageUrl ? `
            <img src="${imageUrl}" alt="${title}" class="thumbnail" 
                 onclick="openModal('${imageUrl.replace(/'/g, "\\'")}')">
          ` : '❌ Sem imagem'}
        </td>
        <td>${title}</td>
        <td>${description}</td>
        <td>${date}</td>
        <td>${location}</td>
        <td>
          <button onclick="viewImage('${imageUrl.replace(/'/g, "\\'")}')">👁️ Ver</button>
          ${(lat && lng) ? `
            <button onclick="viewOnMap(${lat}, ${lng})">🗺️ Mapa</button>
          ` : ''}
        </td>
      </tr>
    `;
  });

  tableHtml += `
      </tbody>
    </table>
  `;

  dataContainer.innerHTML = tableHtml;
}

// Funções para visualização de imagens
function openModal(imageUrl) {
  modalImage.src = imageUrl;
  modal.style.display = 'block';
}

function viewImage(imageUrl) {
  window.open(imageUrl, '_blank');
}

function viewOnMap(lat, lng) {
  window.open(`https://www.google.com/maps?q=${lat},${lng}`, '_blank');
}

// Upload de fotos
photoFiles.addEventListener('change', handleFileSelect);
btnLocation.addEventListener('click', getCurrentLocation);
uploadForm.addEventListener('submit', handleUploadSubmit);

function handleFileSelect(event) {
  selectedFiles = Array.from(event.target.files);
  updateFilePreview();
  updateUploadButton();
}

function updateFilePreview() {
  filePreview.innerHTML = '';
  
  selectedFiles.forEach((file, index) => {
    const reader = new FileReader();
    reader.onload = function(e) {
      const previewItem = document.createElement('div');
      previewItem.className = 'preview-item';
      previewItem.innerHTML = `
        <img src="${e.target.result}" alt="${file.name}">
        <button class="remove-btn" onclick="removeFile(${index})">×</button>
      `;
      filePreview.appendChild(previewItem);
    };
    reader.readAsDataURL(file);
  });
}

function removeFile(index) {
  selectedFiles.splice(index, 1);
  updateFilePreview();
  updateUploadButton();
}

function updateUploadButton() {
  submitUpload.disabled = selectedFiles.length === 0 || !currentLocation;
}

async function getCurrentLocation() {
  if (!navigator.geolocation) {
    showMessage('❌ Geolocalização não suportada neste navegador', 'error');
    return;
  }

  showLoading('Obtendo localização...');
  
  try {
    const position = await new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0
      });
    });

    currentLocation = {
      latitude: position.coords.latitude,
      longitude: position.coords.longitude,
      accuracy: position.coords.accuracy
    };

    locationStatus.textContent = 
      `${currentLocation.latitude.toFixed(6)}, ${currentLocation.longitude.toFixed(6)} (±${currentLocation.accuracy}m)`;
    locationStatus.style.color = '#4ade80';
    
    updateUploadButton();
    showMessage('📍 Localização obtida com sucesso!', 'success', 3000);

  } catch (error) {
    currentLocation = null;
    locationStatus.textContent = 'Erro: ' + error.message;
    locationStatus.style.color = '#ef4444';
    showMessage(`❌ Falha ao obter localização: ${error.message}`, 'error', 5000);
  }
}

async function handleUploadSubmit(event) {
  event.preventDefault();
  
  if (selectedFiles.length === 0) {
    showMessage('❌ Selecione pelo menos uma foto', 'error');
    return;
  }

  if (!currentLocation) {
    showMessage('❌ Obtenha a localização primeiro', 'error');
    return;
  }

  showLoading('Enviando fotos...');
  submitUpload.disabled = true;

  try {
    const formData = new FormData();
    
    // Adicionar arquivos
    selectedFiles.forEach(file => {
      formData.append('photos', file);
    });

    // Adicionar metadados
    formData.append('latitude', currentLocation.latitude);
    formData.append('longitude', currentLocation.longitude);
    formData.append('accuracy', currentLocation.accuracy);
    formData.append('timestamp', new Date().toISOString());

    const response = await fetch(`${SERVER_URL}/api/upload/photos`, {
      method: 'POST',
      body: formData
    });

    const result = await response.json();

    if (response.ok) {
      showUploadResults(result);
      showMessage('✅ Fotos enviadas com sucesso!', 'success', 5000);
      
      // Limpar formulário
      selectedFiles = [];
      photoFiles.value = '';
      filePreview.innerHTML = '';
      currentLocation = null;
      locationStatus.textContent = 'Não obtida';
      locationStatus.style.color = '';
      
    } else {
      throw new Error(result.error || `Erro ${response.status}`);
    }

  } catch (error) {
    showMessage(`❌ Falha no upload: ${error.message}`, 'error', 5000);
    console.error('Erro no upload:', error);
  } finally {
    submitUpload.disabled = false;
  }
}

function showUploadResults(result) {
  uploadResults.style.display = 'block';
  
  let html = `
    <div style="margin-bottom: 15px;">
      <strong>Status:</strong> ${result.success ? '✅ Sucesso' : '❌ Falha'}<br>
      ${result.message ? `<strong>Mensagem:</strong> ${result.message}<br>` : ''}
    </div>
  `;

  if (result.uploaded_files && result.uploaded_files.length > 0) {
    html += '<strong>Arquivos enviados:</strong><ul>';
    result.uploaded_files.forEach(file => {
      html += `<li>${file.original_name} → ${file.cloudinary_url ? 
        `<a href="${file.cloudinary_url}" target="_blank">Ver imagem</a>` : 
        'URL não disponível'}</li>`;
    });
    html += '</ul>';
  }

  if (result.errors && result.errors.length > 0) {
    html += '<strong>Erros:</strong><ul>';
    result.errors.forEach(error => {
      html += `<li>${error}</li>`;
    });
    html += '</ul>';
  }

  uploadResultsContent.innerHTML = html;
}

// Funcionalidade da câmera
async function initCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ 
      video: { 
        width: { ideal: 1280 },
        height: { ideal: 720 },
        facingMode: 'environment' 
      } 
    });
    
    videoElement.srcObject = stream;
    captureBtn.disabled = false;
    showMessage('📷 Câmera inicializada com sucesso!', 'success', 3000);
    
  } catch (error) {
    console.error('Erro ao acessar câmera:', error);
    showMessage(`❌ Não foi possível acessar a câmera: ${error.message}`, 'error', 5000);
    captureBtn.disabled = true;
  }
}

function capturePhoto() {
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  
  canvas.width = videoElement.videoWidth;
  canvas.height = videoElement.videoHeight;
  
  context.drawImage(videoElement, 0, 0, canvas.width, canvas.height);
  
  canvas.toBlob(blob => {
    const fileName = `photo_${Date.now()}.jpg`;
    const file = new File([blob], fileName, { type: 'image/jpeg' });
    
    capturedPhotos.push({
      file: file,
      url: URL.createObjectURL(blob),
      timestamp: new Date()
    });
    
    updateCameraPreview();
    updateCameraSubmitButton();
  }, 'image/jpeg', 0.8);
}

function updateCameraPreview() {
  cameraPreview.innerHTML = '';
  
  capturedPhotos.forEach((photo, index) => {
    const photoElement = document.createElement('div');
    photoElement.className = 'preview-item';
    photoElement.innerHTML = `
      <img src="${photo.url}" alt="Foto ${index + 1}">
      <button class="remove-btn" onclick="removeCameraPhoto(${index})">×</button>
    `;
    cameraPreview.appendChild(photoElement);
  });
  
  clearPhotosBtn.disabled = capturedPhotos.length === 0;
}

function removeCameraPhoto(index) {
  URL.revokeObjectURL(capturedPhotos[index].url);
  capturedPhotos.splice(index, 1);
  updateCameraPreview();
  updateCameraSubmitButton();
}

function clearAllPhotos() {
  capturedPhotos.forEach(photo => URL.revokeObjectURL(photo.url));
  capturedPhotos = [];
  updateCameraPreview();
  updateCameraSubmitButton();
}

async function getCameraLocation() {
  if (!navigator.geolocation) {
    showMessage('❌ Geolocalização não suportada', 'error');
    return;
  }

  showLoading('Obtendo localização...');
  
  try {
    const position = await new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0
      });
    });

    cameraLocation = {
      latitude: position.coords.latitude,
      longitude: position.coords.longitude,
      accuracy: position.coords.accuracy
    };

    cameraLocationStatus.textContent = 
      `${cameraLocation.latitude.toFixed(6)}, ${cameraLocation.longitude.toFixed(6)} (±${cameraLocation.accuracy}m)`;
    cameraLocationStatus.style.color = '#4ade80';
    
    updateCameraSubmitButton();
    showMessage('📍 Localização obtida com sucesso!', 'success', 3000);

  } catch (error) {
    cameraLocation = null;
    cameraLocationStatus.textContent = 'Erro: ' + error.message;
    cameraLocationStatus.style.color = '#ef4444';
    showMessage(`❌ Falha ao obter localização: ${error.message}`, 'error', 5000);
  }
}

function updateCameraSubmitButton() {
  submitCamera.disabled = capturedPhotos.length === 0 || !cameraLocation;
}

async function submitCameraPhotos() {
  if (capturedPhotos.length === 0) {
    showMessage('❌ Capture pelo menos uma foto', 'error');
    return;
  }

  if (!cameraLocation) {
    showMessage('❌ Obtenha a localização primeiro', 'error');
    return;
  }

  showLoading('Enviando fotos capturadas...');
  submitCamera.disabled = true;

  try {
    const formData = new FormData();
    
    // Adicionar arquivos
    capturedPhotos.forEach(photo => {
      formData.append('photos', photo.file);
    });

    // Adicionar metadados
    formData.append('latitude', cameraLocation.latitude);
    formData.append('longitude', cameraLocation.longitude);
    formData.append('accuracy', cameraLocation.accuracy);
    formData.append('timestamp', new Date().toISOString());
    formData.append('source', 'camera');

    const response = await fetch(`${SERVER_URL}/api/upload/photos`, {
      method: 'POST',
      body: formData
    });

    const result = await response.json();

    if (response.ok) {
      showUploadResults(result);
      showMessage('✅ Fotos capturadas enviadas com sucesso!', 'success', 5000);
      
      // Limpar fotos capturadas
      clearAllPhotos();
      cameraLocation = null;
      cameraLocationStatus.textContent = 'Não obtida';
      cameraLocationStatus.style.color = '';
      
    } else {
      throw new Error(result.error || `Erro ${response.status}`);
    }

  } catch (error) {
    showMessage(`❌ Falha no upload: ${error.message}`, 'error', 5000);
    console.error('Erro no upload:', error);
  } finally {
    submitCamera.disabled = false;
  }
}

// Monitoramento
async function checkHealth() {
  showMonitoringResults('Verificando saúde do servidor...');
  
  try {
    const result = await makeRequest('/health');
    healthStatus.textContent = result.status;
    healthStatus.style.color = result.status === 'healthy' ? '#4ade80' : 
                              result.status === 'degraded' ? '#fbbf24' : '#ef4444';
    
    showMonitoringResults(JSON.stringify(result, null, 2));
    
  } catch (error) {
    healthStatus.textContent = 'offline';
    healthStatus.style.color = '#ef4444';
    showMonitoringResults(`Erro: ${error.message}`);
  }
}

async function checkEnvironment() {
  showMonitoringResults('Verificando variáveis de ambiente...');
  
  try {
    const result = await makeRequest('/debug/environment');
    showMonitoringResults(JSON.stringify(result, null, 2));
  } catch (error) {
    showMonitoringResults(`Erro: ${error.message}`);
  }
}

async function checkCredentials() {
  showMonitoringResults('Verificando credenciais...');
  
  try {
    const result = await makeRequest('/debug/credentials');
    showMonitoringResults(JSON.stringify(result, null, 2));
  } catch (error) {
    showMonitoringResults(`Erro: ${error.message}`);
  }
}

async function checkCloudinary() {
  showMonitoringResults('Verificando configuração do Cloudinary...');
  
  try {
    const result = await makeRequest('/debug/cloudinary');
    showMonitoringResults(JSON.stringify(result, null, 2));
  } catch (error) {
    showMonitoringResults(`Erro: ${error.message}`);
  }
}

async function getMetrics() {
  showMonitoringResults('Buscando métricas...');
  
  try {
    const result = await makeRequest('/metrics');
    showMonitoringResults(result);
  } catch (error) {
    showMonitoringResults(`Erro: ${error.message}`);
  }
}

function showMonitoringResults(data) {
  monitoringResults.style.display = 'block';
  monitoringData.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
}

// Alternar entre abas
function switchTab(tabName) {
  // Esconder todos os conteúdos de abas
  tabContents.forEach(tab => tab.classList.remove('active'));
  tabs.forEach(tab => tab.classList.remove('active'));
  
  // Mostrar a aba selecionada
  document.getElementById(`tab-${tabName}`).classList.add('active');
  document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
  
  // Inicializar câmera se for a aba de câmera
  if (tabName === 'camera' && !stream) {
    initCamera();
  }
}

// Modal
modalClose.addEventListener('click', () => {
  modal.style.display = 'none';
});

window.addEventListener('click', (event) => {
  if (event.target === modal) {
    modal.style.display = 'none';
  }
});

// Event Listeners
btnTest.addEventListener('click', testConnection);
btnLoad.addEventListener('click', loadData);
btnRefresh.addEventListener('click', loadData);

tabs.forEach(tab => {
  tab.addEventListener('click', () => {
    switchTab(tab.dataset.tab);
  });
});

searchInput.addEventListener('input', filterData);
entriesSelect.addEventListener('change', filterData);

// Câmera
captureBtn.addEventListener('click', capturePhoto);
clearPhotosBtn.addEventListener('click', clearAllPhotos);
btnCameraLocation.addEventListener('click', getCameraLocation);
submitCamera.addEventListener('click', submitCameraPhotos);

// Monitoramento
btnHealthCheck.addEventListener('click', checkHealth);
btnEnvCheck.addEventListener('click', checkEnvironment);
btnCredsCheck.addEventListener('click', checkCredentials);
btnCloudinaryCheck.addEventListener('click', checkCloudinary);
btnMetrics.addEventListener('click', getMetrics);
btnOtelMetrics.addEventListener('click', getOtelMetrics);
btnSystemMetrics.addEventListener('click', getSystemMetrics);
btnAutoMetrics.addEventListener('click', toggleAutoMetrics);

// Filtro de dados
function filterData() {
  const searchTerm = searchInput.value.toLowerCase();
  const entries = parseInt(entriesSelect.value);
  
  let filteredData = imageData;
  
  if (searchTerm) {
    filteredData = imageData.filter(item => 
      (item.Título && item.Título.toLowerCase().includes(searchTerm)) ||
      (item.Descrição && item.Descrição.toLowerCase().includes(searchTerm)) ||
      (item['Nome do Arquivo Original'] && item['Nome do Arquivo Original'].toLowerCase().includes(searchTerm))
    );
  }
  
  filteredData = filteredData.slice(0, entries);
  displayData(filteredData);
}

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
  showMessage('👋 Bem-vindo! Clique em <strong>Testar Conexão</strong> para começar.');
  
  // Verificar se temos permissão de câmera prévia
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    // A câmera será inicializada quando a aba for clicada
    console.log('Câmera disponível');
  } else {
    console.warn('Câmera não disponível');
  }
});

// Funções para auto atualização de métricas
function toggleAutoMetrics() {
    if (autoMetricsEnabled) {
        // Parar auto atualização
        clearInterval(metricsInterval);
        autoMetricsEnabled = false;
        btnAutoMetrics.textContent = '🔄 Auto Atualizar';
        showMessage('⏹️ Auto atualização parada', 'info', 3000);
    } else {
        // Iniciar auto atualização
        autoMetricsEnabled = true;
        btnAutoMetrics.textContent = '⏹️ Parar Auto';
        showMessage('🔄 Auto atualização iniciada', 'success', 3000);
        
        // Buscar métricas imediatamente
        getOtelMetrics();
        
        // Configurar intervalo
        metricsInterval = setInterval(() => {
            getOtelMetrics();
        }, 5000); // Atualizar a cada 5 segundos
    }
}

// Inicializar gráficos
function initCharts() {
    const cpuCtx = document.getElementById('cpuChart').getContext('2d');
    const memoryCtx = document.getElementById('memoryChart').getContext('2d');
    
    cpuChart = new Chart(cpuCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Uso de CPU (%)',
                data: [],
                borderColor: 'rgb(59, 130, 246)',
                tension: 0.1,
                fill: true,
                backgroundColor: 'rgba(59, 130, 246, 0.1)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100
                }
            }
        }
    });
    
    memoryChart = new Chart(memoryCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Uso de Memória (%)',
                data: [],
                borderColor: 'rgb(163, 230, 53)',
                tension: 0.1,
                fill: true,
                backgroundColor: 'rgba(163, 230, 53, 0.1)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100
                }
            }
        }
    });
}

// Atualizar gráficos com novas métricas
function updateCharts(metrics) {
    if (!metrics.system) return;
    
    const now = new Date().toLocaleTimeString();
    
    // Adicionar novos dados
    metricHistory.cpu.push(metrics.system.cpu_percent);
    metricHistory.memory.push(metrics.system.memory_percent);
    metricHistory.timestamps.push(now);
    
    // Manter apenas os últimos 20 pontos
    if (metricHistory.cpu.length > 20) {
        metricHistory.cpu.shift();
        metricHistory.memory.shift();
        metricHistory.timestamps.shift();
    }
    
    // Atualizar gráficos
    if (cpuChart && memoryChart) {
        cpuChart.data.labels = metricHistory.timestamps;
        cpuChart.data.datasets[0].data = metricHistory.cpu;
        cpuChart.update();
        
        memoryChart.data.labels = metricHistory.timestamps;
        memoryChart.data.datasets[0].data = metricHistory.memory;
        memoryChart.update();
    }
}

// Inicializar gráficos quando a página carregar
document.addEventListener('DOMContentLoaded', initCharts);

// Mostrar/ocultar gráficos
function toggleMetricsCharts(show) {
    const chartsContainer = document.getElementById('metricsCharts');
    chartsContainer.style.display = show ? 'block' : 'none';
}