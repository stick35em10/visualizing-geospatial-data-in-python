// Base Camera Manager - Add this to your existing JavaScript
class CameraManager {
    constructor() {
        this.video = document.getElementById('cameraVideo');
        this.canvas = document.getElementById('cameraCanvas');
        this.photosGrid = document.getElementById('photosGrid');
        this.stream = null;
        this.isActive = false;
        this.capturedPhotos = [];
        this.currentCameraIndex = 0;
        this.availableCameras = [];
        
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        const startBtn = document.getElementById('startCameraBtn');
        const stopBtn = document.getElementById('stopCameraBtn');
        const captureBtn = document.getElementById('capturePhotoBtn');
        const switchBtn = document.getElementById('switchCameraBtn');
        
        if (startBtn) startBtn.addEventListener('click', () => this.startCamera());
        if (stopBtn) stopBtn.addEventListener('click', () => this.stopCamera());
        if (captureBtn) captureBtn.addEventListener('click', () => this.capturePhoto());
        if (switchBtn) switchBtn.addEventListener('click', () => this.switchCamera());
    }
    
    async startCamera() {
        try {
            // Get available cameras
            this.availableCameras = await this.getAvailableCameras();
            
            // Request camera access
            const constraints = {
                video: {
                    deviceId: this.availableCameras[this.currentCameraIndex]?.deviceId
                },
                audio: false
            };
            
            this.stream = await navigator.mediaDevices.getUserMedia(constraints);
            this.video.srcObject = this.stream;
            
            this.isActive = true;
            this.updateButtons(true);
            
            // Show camera section
            const cameraSection = document.getElementById('cameraSection');
            if (cameraSection) cameraSection.style.display = 'block';
            
            showMessage('📹 Câmera iniciada com sucesso!', 'success');
            
        } catch (error) {
            console.error('Error starting camera:', error);
            showMessage('❌ Erro ao iniciar câmera: ' + error.message, 'error');
        }
    }
    
    stopCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        
        this.isActive = false;
        this.updateButtons(false);
        this.video.srcObject = null;
        
        showMessage('⏹️ Câmera parada', 'warning', 2000);
    }
    
    updateButtons(cameraActive) {
        const startBtn = document.getElementById('startCameraBtn');
        const stopBtn = document.getElementById('stopCameraBtn');
        const captureBtn = document.getElementById('capturePhotoBtn');
        const switchBtn = document.getElementById('switchCameraBtn');
        
        if (startBtn) startBtn.style.display = cameraActive ? 'none' : 'inline-block';
        if (stopBtn) stopBtn.style.display = cameraActive ? 'inline-block' : 'none';
        if (captureBtn) captureBtn.disabled = !cameraActive;
        if (switchBtn) switchBtn.disabled = !cameraActive || this.availableCameras.length <= 1;
    }
    
    async capturePhoto() {
        if (!this.isActive || !this.video) {
            showMessage('❌ Câmera não está ativa', 'error');
            return;
        }
        
        try {
            // Set canvas size to match video
            const canvas = this.canvas;
            const ctx = canvas.getContext('2d');
            canvas.width = this.video.videoWidth;
            canvas.height = this.video.videoHeight;
            
            // Draw current video frame to canvas
            ctx.drawImage(this.video, 0, 0);
            
            // Convert to blob
            canvas.toBlob((blob) => {
                const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
                const file = new File([blob], `camera_${timestamp}.jpg`, { type: 'image/jpeg' });
                
                this.capturedPhotos.push({
                    file: file,
                    url: URL.createObjectURL(blob),
                    timestamp: new Date()
                });
                
                this.updatePhotosDisplay();
                showMessage('📸 Foto capturada!', 'success', 2000);
                
                // Add to file upload list if it exists
                if (typeof addFiles === 'function') {
                    addFiles([file]);
                }
                
            }, 'image/jpeg', 0.8);
            
        } catch (error) {
            console.error('Error capturing photo:', error);
            showMessage('❌ Erro ao capturar foto', 'error');
        }
    }
    
    updatePhotosDisplay() {
        if (!this.photosGrid) return;
        
        this.photosGrid.innerHTML = '';
        
        this.capturedPhotos.forEach((photo, index) => {
            const photoItem = document.createElement('div');
            photoItem.className = 'photo-item';
            photoItem.innerHTML = `
                <img src="${photo.url}" alt="Foto ${index + 1}">
                <div class="photo-actions">
                    <button class="photo-action-btn" onclick="cameraManager.viewPhoto(${index})" title="Visualizar">👁️</button>
                    <button class="photo-action-btn" onclick="cameraManager.deletePhoto(${index})" title="Excluir">🗑️</button>
                </div>
            `;
            
            this.photosGrid.appendChild(photoItem);
        });
    }
    
    viewPhoto(index) {
        const photo = this.capturedPhotos[index];
        if (photo && typeof showImageModal === 'function') {
            showImageModal(photo.url);
        }
    }
    
    deletePhoto(index) {
        if (confirm('Deseja excluir esta foto?')) {
            const photo = this.capturedPhotos[index];
            URL.revokeObjectURL(photo.url);
            this.capturedPhotos.splice(index, 1);
            this.updatePhotosDisplay();
            showMessage('🗑️ Foto excluída', 'warning', 2000);
        }
    }
    
    async switchCamera() {
        if (this.availableCameras.length <= 1) return;
        
        this.currentCameraIndex = (this.currentCameraIndex + 1) % this.availableCameras.length;
        
        // Restart camera with new device
        this.stopCamera();
        setTimeout(() => this.startCamera(), 100);
    }
    
    async getAvailableCameras() {
        try {
            const devices = await navigator.mediaDevices.enumerateDevices();
            return devices.filter(device => device.kind === 'videoinput');
        } catch (error) {
            console.error('Error getting cameras:', error);
            return [];
        }
    }
    
    cleanup() {
        this.stopCamera();
        this.capturedPhotos.forEach(photo => URL.revokeObjectURL(photo.url));
        this.capturedPhotos = [];
    }
}

// Global camera manager instance
let cameraManager;