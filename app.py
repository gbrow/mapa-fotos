import sys
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
import os
import exifread
from flask import Flask, jsonify, send_file, send_from_directory, request
from flask_cors import CORS
from PIL import Image, ImageOps
import json
import requests
from io import BytesIO
import os

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Configurações
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FOTOS_FOLDER = os.path.join(BASE_DIR, 'fotos')
THUMBNAIL_FOLDER = os.path.join(BASE_DIR, 'thumbnails')
CACHE_FILE = os.path.join(BASE_DIR, 'fotos_cache.json')

# Criar pastas se não existirem
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)
os.makedirs(FOTOS_FOLDER, exist_ok=True)

THUMBNAIL_SIZE = (300, 300)

def extrair_coordenadas(tags):
    """Extrai coordenadas GPS dos metadados EXIF"""
    def obter_gps_valor(tag):
        try:
            degrees = tag.values[0].num / tag.values[0].den
            minutes = tag.values[1].num / tag.values[1].den
            seconds = tag.values[2].num / tag.values[2].den
            return degrees + (minutes / 60.0) + (seconds / 3600.0)
        except:
            return None
    
    latitude = None
    longitude = None
    
    if 'GPS GPSLatitude' in tags and 'GPS GPSLongitude' in tags:
        latitude = obter_gps_valor(tags['GPS GPSLatitude'])
        longitude = obter_gps_valor(tags['GPS GPSLongitude'])
        
        if latitude is not None and longitude is not None:
            if 'GPS GPSLatitudeRef' in tags and tags['GPS GPSLatitudeRef'].values == 'S':
                latitude = -latitude
            if 'GPS GPSLongitudeRef' in tags and tags['GPS GPSLongitudeRef'].values == 'W':
                longitude = -longitude
    
    return latitude, longitude

def processar_fotos():
    """Processa todas as fotos na pasta"""
    fotos_data = []
    
    if not os.path.exists(FOTOS_FOLDER):
        print(f"⚠️  Pasta 'fotos' não encontrada")
        return fotos_data
    
    arquivos = os.listdir(FOTOS_FOLDER)
    print(f"📁 Encontrados {len(arquivos)} arquivos")
    
    for filename in arquivos:
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            caminho = os.path.join(FOTOS_FOLDER, filename)
            
            try:
                with open(caminho, 'rb') as f:
                    tags = exifread.process_file(f, details=False)
                
                lat, lon = extrair_coordenadas(tags)
                
                if lat is not None and lon is not None:
                    # Criar thumbnail
                    thumb_path = os.path.join(THUMBNAIL_FOLDER, filename)
                    if not os.path.exists(thumb_path):
                        with Image.open(caminho) as img:
                            img = ImageOps.exif_transpose(img)
                            img.thumbnail(THUMBNAIL_SIZE)
                            if img.mode in ('RGBA', 'LA', 'P'):
                                img = img.convert('RGB')
                            img.save(thumb_path, 'JPEG', quality=85)
                    
                    fotos_data.append({
                        'filename': filename,
                        'latitude': float(lat),
                        'longitude': float(lon),
                        'thumbnail': f'/thumbnail/{filename}',
                        'full_image': f'/foto/{filename}',
                        'data_tirada': str(tags.get('EXIF DateTimeOriginal', ''))
                    })
                    
            except Exception as e:
                print(f"❌ Erro em {filename}: {e}")
    
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(fotos_data, f, ensure_ascii=False, indent=2)
    
    return fotos_data


# Configurações do Google Drive
DRIVE_FOLDER_ID = "1SVEBHhbeQ4R3_QJLx7cHU93qBUFOa1g2"  # Cole o ID aqui
DRIVE_API_KEY = os.environ.get('GOOGLE_DRIVE_API_KEY', '')  # Opcional

def listar_arquivos_drive():
    """Lista arquivos da pasta do Google Drive"""
    url = f"https://www.googleapis.com/drive/v3/files"
    params = {
        'q': f"'{DRIVE_FOLDER_ID}' in parents",
        'key': DRIVE_API_KEY if DRIVE_API_KEY else None,
        'fields': 'files(id, name, mimeType, size)'
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json().get('files', [])
    except Exception as e:
        print(f"Erro ao acessar Google Drive: {e}")
    
    return []

def baixar_do_drive(file_id, filename):
    """Baixa um arquivo do Google Drive"""
    # URL para download direto
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    
    try:
        response = requests.get(download_url, stream=True)
        if response.status_code == 200:
            caminho_local = os.path.join(FOTOS_FOLDER, filename)
            
            # Salvar arquivo localmente (temporário)
            with open(caminho_local, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return caminho_local
    except Exception as e:
        print(f"Erro ao baixar {filename}: {e}")
    
    return None

def processar_fotos_do_drive():
    """Processa fotos diretamente do Google Drive"""
    arquivos_drive = listar_arquivos_drive()
    fotos_data = []
    
    for arquivo in arquivos_drive:
        filename = arquivo['name']
        
        # Verificar se é imagem
        if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.heic')):
            continue
        
        print(f"📥 Processando do Drive: {filename}")
        
        # Baixar arquivo temporariamente
        caminho_temp = baixar_do_drive(arquivo['id'], filename)
        if not caminho_temp:
            continue
        
        try:
            # Extrair EXIF
            with open(caminho_temp, 'rb') as f:
                tags = exifread.process_file(f, details=False)
            
            lat, lon = extrair_coordenadas(tags)
            
            if lat is not None and lon is not None:
                # Criar thumbnail (salva localmente)
                thumb_path = os.path.join(THUMBNAIL_FOLDER, filename)
                if not os.path.exists(thumb_path):
                    with Image.open(caminho_temp) as img:
                        img = ImageOps.exif_transpose(img)
                        img.thumbnail(THUMBNAIL_SIZE)
                        if img.mode in ('RGBA', 'LA', 'P'):
                            img = img.convert('RGB')
                        img.save(thumb_path, 'JPEG', quality=85)
                
                # URL direta para a imagem no Drive (para visualização)
                drive_url = f"https://drive.google.com/uc?export=view&id={arquivo['id']}"
                
                fotos_data.append({
                    'filename': filename,
                    'latitude': float(lat),
                    'longitude': float(lon),
                    'thumbnail': f'/thumbnail/{filename}',  # Thumb local
                    'full_image': drive_url,  # Imagem original do Drive
                    'data_tirada': str(tags.get('EXIF DateTimeOriginal', ''))
                })
                
        except Exception as e:
            print(f"❌ Erro ao processar {filename}: {e}")
        
        # Remover arquivo temporário
        try:
            os.remove(caminho_temp)
        except:
            pass
    
    return fotos_data

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

#@app.route('/api/fotos')
#def listar_fotos():
#    try:
#        if os.path.exists(CACHE_FILE):
#            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
#                return jsonify(json.load(f))
#    except:
#        pass
#    
#    return jsonify(processar_fotos())

@app.route('/api/fotos')
def listar_fotos():
    """Retorna lista de fotos (do Drive ou local)"""
    # Usar Drive se configurado
    if DRIVE_FOLDER_ID:
        return jsonify(processar_fotos_do_drive())
    
    # Fallback para local
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
    except:
        pass
    
    return jsonify(processar_fotos())

@app.route('/foto/<nome_arquivo>')
def servir_foto(nome_arquivo):
    caminho = os.path.join(FOTOS_FOLDER, nome_arquivo)
    if os.path.exists(caminho):
        return send_file(caminho, mimetype='image/jpeg')
    return 'Foto não encontrada', 404

@app.route('/thumbnail/<nome_arquivo>')
def servir_thumbnail(nome_arquivo):
    caminho = os.path.join(THUMBNAIL_FOLDER, nome_arquivo)
    if os.path.exists(caminho):
        return send_file(caminho, mimetype='image/jpeg')
    
    caminho_original = os.path.join(FOTOS_FOLDER, nome_arquivo)
    if os.path.exists(caminho_original):
        return send_file(caminho_original, mimetype='image/jpeg')
    
    return 'Thumbnail não encontrada', 404

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    """Página para upload de múltiplas fotos"""
    if request.method == 'POST':
        # Verificar se o campo 'fotos' existe (agora no plural)
        if 'fotos' not in request.files:
            return '''
                <html>
                <body style="font-family: Arial; padding: 20px;">
                    <h1>❌ Erro no upload</h1>
                    <p>Nenhum arquivo selecionado.</p>
                    <a href="/upload">Tentar novamente</a>
                </body>
                </html>
            '''
        
        arquivos = request.files.getlist('fotos')
        uploads_sucesso = []
        uploads_falha = []
        
        # Processar cada arquivo
        for arquivo in arquivos:
            # Pular se não tiver nome
            if arquivo.filename == '':
                continue
            
            # Verificar extensão
            if arquivo and arquivo.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.heic', '.jfif')):
                try:
                    from werkzeug.utils import secure_filename
                    filename = secure_filename(arquivo.filename)
                    caminho = os.path.join(FOTOS_FOLDER, filename)
                    
                    # Salvar arquivo
                    arquivo.save(caminho)
                    uploads_sucesso.append(filename)
                    
                    print(f"✅ Upload realizado: {filename}")
                    
                except Exception as e:
                    print(f"❌ Erro ao salvar {arquivo.filename}: {e}")
                    uploads_falha.append(f"{arquivo.filename} - {str(e)}")
            else:
                uploads_falha.append(f"{arquivo.filename} - Formato não suportado")
        
        # Se houve uploads, reprocessar todas as fotos
        if uploads_sucesso:
            print("🔄 Reprocessando fotos após upload...")
            processar_fotos()
        
        # Gerar relatório
        return f'''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Resultado do Upload</title>
                <style>
                    body {{ font-family: Arial, sans-serif; padding: 30px; max-width: 800px; margin: 0 auto; }}
                    .success {{ color: #2ecc71; background: #d5f4e6; padding: 10px; border-radius: 5px; margin: 10px 0; }}
                    .error {{ color: #e74c3c; background: #fadbd8; padding: 10px; border-radius: 5px; margin: 10px 0; }}
                    .summary {{ background: #e8f4fc; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                    .btn {{ 
                        display: inline-block; 
                        background: #3498db; 
                        color: white; 
                        padding: 12px 24px; 
                        text-decoration: none; 
                        border-radius: 5px; 
                        margin: 10px 5px;
                        border: none;
                        cursor: pointer;
                    }}
                    .btn-primary {{ background: #2c3e50; }}
                    .file-list {{ 
                        background: #f8f9fa; 
                        padding: 15px; 
                        border-radius: 5px; 
                        max-height: 300px; 
                        overflow-y: auto;
                        font-family: monospace;
                    }}
                </style>
            </head>
            <body>
                <h1>📊 Resultado do Upload</h1>
                
                <div class="summary">
                    <h3>📈 Resumo</h3>
                    <p><strong>Sucesso:</strong> {len(uploads_sucesso)} foto(s)</p>
                    <p><strong>Falha:</strong> {len(uploads_falha)} foto(s)</p>
                    <p><strong>Total processado:</strong> {len(arquivos)} arquivo(s)</p>
                </div>
                
                {f'''
                <div class="success">
                    <h3>✅ Uploads realizados com sucesso:</h3>
                    <div class="file-list">
                        {"<br>".join([f"✓ {f}" for f in uploads_sucesso])}
                    </div>
                </div>
                ''' if uploads_sucesso else ''}
                
                {f'''
                <div class="error">
                    <h3>❌ Uploads que falharam:</h3>
                    <div class="file-list">
                        {"<br>".join([f"✗ {f}" for f in uploads_falha])}
                    </div>
                </div>
                ''' if uploads_falha else ''}
                
                <div style="margin-top: 30px;">
                    <a href="/" class="btn">🗺️ Ver Mapa</a>
                    <a href="/upload" class="btn">📤 Fazer Novo Upload</a>
                    <button onclick="location.reload()" class="btn btn-primary">🔄 Atualizar Mapa</button>
                </div>
                
                <div style="margin-top: 30px; color: #666; font-size: 14px;">
                    <p><strong>💡 Dica:</strong> Clique em "Atualizar Mapa" para ver as novas fotos no mapa.</p>
                    <p>As fotos serão processadas automaticamente para extrair coordenadas GPS.</p>
                </div>
            </body>
            </html>
        '''
    
    # GET request - mostrar formulário
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Upload de Fotos</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                padding: 40px;
                max-width: 800px;
                margin: 0 auto;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }
            
            .container {
                background: white;
                padding: 40px;
                border-radius: 15px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            }
            
            h1 {
                color: #2c3e50;
                margin-bottom: 10px;
            }
            
            .subtitle {
                color: #7f8c8d;
                margin-bottom: 30px;
            }
            
            .upload-area {
                border: 3px dashed #3498db;
                border-radius: 10px;
                padding: 40px;
                text-align: center;
                margin: 30px 0;
                background: #f8f9fa;
                transition: all 0.3s;
                cursor: pointer;
            }
            
            .upload-area:hover {
                background: #e8f4fc;
                border-color: #2980b9;
            }
            
            .upload-area.drag-over {
                background: #d6eaf8;
                border-color: #1abc9c;
                transform: scale(1.02);
            }
            
            .upload-icon {
                font-size: 48px;
                color: #3498db;
                margin-bottom: 15px;
            }
            
            #file-list {
                margin-top: 20px;
                max-height: 200px;
                overflow-y: auto;
                text-align: left;
            }
            
            .file-item {
                padding: 8px;
                margin: 5px 0;
                background: #f1f8ff;
                border-radius: 5px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .file-item .remove {
                color: #e74c3c;
                cursor: pointer;
                background: none;
                border: none;
                font-size: 18px;
            }
            
            .file-item .remove:hover {
                color: #c0392b;
            }
            
            .btn {
                display: inline-block;
                background: #2c3e50;
                color: white;
                padding: 14px 28px;
                text-decoration: none;
                border-radius: 8px;
                border: none;
                cursor: pointer;
                font-size: 16px;
                font-weight: 600;
                transition: all 0.3s;
                margin: 10px 5px;
            }
            
            .btn:hover {
                background: #1a252f;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }
            
            .btn-primary {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            
            .btn-primary:hover {
                background: linear-gradient(135deg, #5a6fd8 0%, #6a4190 100%);
            }
            
            .btn-secondary {
                background: #95a5a6;
            }
            
            .btn-secondary:hover {
                background: #7f8c8d;
            }
            
            .info-box {
                background: #e8f4fc;
                padding: 20px;
                border-radius: 10px;
                margin-top: 30px;
                border-left: 5px solid #3498db;
            }
            
            .progress-bar {
                width: 100%;
                height: 20px;
                background: #ecf0f1;
                border-radius: 10px;
                margin: 20px 0;
                overflow: hidden;
                display: none;
            }
            
            .progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #2ecc71, #1abc9c);
                width: 0%;
                transition: width 0.3s;
            }
            
            #progress-text {
                text-align: center;
                margin-top: 10px;
                color: #7f8c8d;
                display: none;
            }
            
            .formats {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin: 15px 0;
            }
            
            .format-tag {
                background: #e3f2fd;
                color: #1976d2;
                padding: 5px 10px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 600;
            }
            
            @media (max-width: 600px) {
                body {
                    padding: 20px;
                }
                
                .container {
                    padding: 20px;
                }
                
                .upload-area {
                    padding: 20px;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📤 Upload em Lote</h1>
            <p class="subtitle">Selecione múltiplas fotos de uma vez</p>
            
            <form id="upload-form" method="post" enctype="multipart/form-data">
                <!-- Área de drag & drop -->
                <div class="upload-area" id="drop-area">
                    <div class="upload-icon">📁</div>
                    <h3>Arraste e solte suas fotos aqui</h3>
                    <p>ou</p>
                    <label for="file-input" class="btn">
                        📷 Selecionar Fotos
                    </label>
                    <input type="file" id="file-input" name="fotos" multiple 
                           accept=".jpg,.jpeg,.png,.heic,.jfif" style="display: none;">
                    <p style="margin-top: 15px; color: #7f8c8d; font-size: 14px;">
                        Suporte para múltiplos arquivos
                    </p>
                </div>
                
                <!-- Lista de arquivos selecionados -->
                <div id="file-list-container">
                    <h4>Arquivos selecionados: <span id="file-count">0</span></h4>
                    <div id="file-list"></div>
                </div>
                
                <!-- Barra de progresso (para futura implementação com AJAX) -->
                <div class="progress-bar">
                    <div class="progress-fill" id="progress-fill"></div>
                </div>
                <div id="progress-text"></div>
                
                <!-- Botões de ação -->
                <div style="margin-top: 30px; text-align: center;">
                    <button type="submit" class="btn btn-primary" id="submit-btn">
                        🚀 Enviar Todas as Fotos
                    </button>
                    <button type="button" class="btn btn-secondary" onclick="clearFiles()">
                        🗑️ Limpar Seleção
                    </button>
                    <a href="/" class="btn">↩️ Voltar ao Mapa</a>
                </div>
            </form>
            
            <!-- Informações -->
            <div class="info-box">
                <h3>💡 Informações importantes:</h3>
                <div class="formats">
                    <span class="format-tag">JPG</span>
                    <span class="format-tag">JPEG</span>
                    <span class="format-tag">PNG</span>
                    <span class="format-tag">HEIC</span>
                    <span class="format-tag">JFIF</span>
                </div>
                <ul style="margin: 15px 0; padding-left: 20px;">
                    <li>Selecione múltiplas fotos segurando <kbd>Ctrl</kbd> (Windows) ou <kbd>Cmd</kbd> (Mac)</li>
                    <li>Ou arraste e solte diretamente na área acima</li>
                    <li>Tamanho máximo por arquivo: 10MB</li>
                    <li>Total máximo por upload: 50MB</li>
                    <li>Apenas fotos com coordenadas GPS aparecerão no mapa</li>
                    <li>Após o upload, atualize a página do mapa para ver as fotos</li>
                </ul>
                <p><strong>📊 Status atual:</strong> <span id="total-fotos">0</span> fotos no sistema</p>
            </div>
        </div>
        
        <script>
            // Elementos DOM
            const dropArea = document.getElementById('drop-area');
            const fileInput = document.getElementById('file-input');
            const fileList = document.getElementById('file-list');
            const fileCount = document.getElementById('file-count');
            const totalFotos = document.getElementById('total-fotos');
            const form = document.getElementById('upload-form');
            const submitBtn = document.getElementById('submit-btn');
            
            // Array para armazenar arquivos
            let files = [];
            
            // Atualizar contador
            function updateFileCount() {
                fileCount.textContent = files.length;
                submitBtn.disabled = files.length === 0;
                submitBtn.textContent = files.length === 0 
                    ? 'Selecione fotos primeiro' 
                    : `🚀 Enviar ${files.length} foto(s)`;
            }
            
            // Adicionar arquivo à lista
            function addFileToList(file) {
                const fileItem = document.createElement('div');
                fileItem.className = 'file-item';
                fileItem.innerHTML = `
                    <span>${file.name} (${formatBytes(file.size)})</span>
                    <button type="button" class="remove" onclick="removeFile('${file.name}')">×</button>
                `;
                fileList.appendChild(fileItem);
            }
            
            // Remover arquivo
            window.removeFile = function(filename) {
                files = files.filter(f => f.name !== filename);
                renderFileList();
            }
            
            // Limpar todos os arquivos
            window.clearFiles = function() {
                files = [];
                renderFileList();
                fileInput.value = '';
            }
            
            // Renderizar lista de arquivos
            function renderFileList() {
                fileList.innerHTML = '';
                files.forEach(addFileToList);
                updateFileCount();
            }
            
            // Formatar bytes para KB/MB
            function formatBytes(bytes) {
                if (bytes === 0) return '0 Bytes';
                const k = 1024;
                const sizes = ['Bytes', 'KB', 'MB', 'GB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
            }
            
            // Evento: Selecionar arquivos via input
            fileInput.addEventListener('change', (e) => {
                const newFiles = Array.from(e.target.files);
                
                // Validar tamanho total
                const totalSize = newFiles.reduce((sum, file) => sum + file.size, 0);
                if (totalSize > 50 * 1024 * 1024) { // 50MB
                    alert('❌ O tamanho total dos arquivos excede 50MB');
                    return;
                }
                
                // Validar cada arquivo
                newFiles.forEach(file => {
                    if (file.size > 10 * 1024 * 1024) { // 10MB por arquivo
                        alert(`❌ O arquivo "${file.name}" excede 10MB`);
                        return;
                    }
                    
                    // Verificar se já existe
                    if (!files.some(f => f.name === file.name)) {
                        files.push(file);
                    }
                });
                
                renderFileList();
            });
            
            // Eventos para drag & drop
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                dropArea.addEventListener(eventName, preventDefaults, false);
            });
            
            function preventDefaults(e) {
                e.preventDefault();
                e.stopPropagation();
            }
            
            ['dragenter', 'dragover'].forEach(eventName => {
                dropArea.addEventListener(eventName, () => {
                    dropArea.classList.add('drag-over');
                }, false);
            });
            
            ['dragleave', 'drop'].forEach(eventName => {
                dropArea.addEventListener(eventName, () => {
                    dropArea.classList.remove('drag-over');
                }, false);
            });
            
            // Evento: Drop de arquivos
            dropArea.addEventListener('drop', (e) => {
                const dt = e.dataTransfer;
                const droppedFiles = dt.files;
                
                // Converter FileList para Array e adicionar ao input
                const dataTransfer = new DataTransfer();
                files.forEach(f => dataTransfer.items.add(f));
                
                for (let file of droppedFiles) {
                    if (!files.some(f => f.name === file.name)) {
                        dataTransfer.items.add(file);
                        files.push(file);
                    }
                }
                
                fileInput.files = dataTransfer.files;
                renderFileList();
            });
            
            // Clique na área ativa o input
            dropArea.addEventListener('click', () => {
                fileInput.click();
            });
            
            // Carregar quantidade de fotos existentes
            fetch('/api/fotos')
                .then(response => response.json())
                .then(data => {
                    totalFotos.textContent = data.length;
                })
                .catch(error => {
                    console.error('Erro ao carregar fotos:', error);
                });
            
            // Submit do formulário
            form.addEventListener('submit', (e) => {
                if (files.length === 0) {
                    e.preventDefault();
                    alert('Selecione pelo menos uma foto para enviar.');
                    return;
                }
                
                // Mostrar mensagem de processamento
                submitBtn.disabled = true;
                submitBtn.innerHTML = '⏳ Processando...';
                
                // O formulário será enviado normalmente
                // (Para upload progressivo com barra, seria necessário AJAX)
            });
            
            // Inicializar
            updateFileCount();
        </script>
    </body>
    </html>
    '''
@app.route('/api/upload-chunk', methods=['POST'])
def upload_chunk():
    """Upload em chunks para arquivos grandes (opcional)"""
    chunk = request.files.get('chunk')
    filename = request.form.get('filename')
    chunk_index = int(request.form.get('chunk_index', 0))
    total_chunks = int(request.form.get('total_chunks', 1))
    
    # Criar pasta temporária para chunks
    temp_dir = os.path.join(BASE_DIR, 'temp_uploads')
    os.makedirs(temp_dir, exist_ok=True)
    
    # Salvar chunk
    chunk_path = os.path.join(temp_dir, f'{filename}.part{chunk_index}')
    chunk.save(chunk_path)
    
    # Se for o último chunk, combinar todos
    if chunk_index == total_chunks - 1:
        final_path = os.path.join(FOTOS_FOLDER, filename)
        with open(final_path, 'wb') as f:
            for i in range(total_chunks):
                part_path = os.path.join(temp_dir, f'{filename}.part{i}')
                with open(part_path, 'rb') as part:
                    f.write(part.read())
                os.remove(part_path)  # Remover chunk após combinar
        
        # Processar a nova foto
        processar_fotos()
        
        return jsonify({
            'success': True,
            'filename': filename,
            'message': 'Upload completo'
        })
    
    return jsonify({
        'success': True,
        'chunk_received': chunk_index,
        'message': f'Chunk {chunk_index + 1}/{total_chunks} recebido'
    })
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 60)
    print("🚀 Servidor Mapa de Fotos")
    print("=" * 60)
    print(f"📂 Pasta fotos: {FOTOS_FOLDER}")
    
    # Processar fotos existentes
    if os.path.exists(FOTOS_FOLDER):
        print("📸 Processando fotos...")
        fotos = processar_fotos()
        print(f"✅ {len(fotos)} fotos processadas")
    else:
        print("ℹ️  Pasta 'fotos' vazia")
        print("👉 Use /upload para enviar fotos")
    
    print(f"🌐 Acesse: http://localhost:{port}")
    print("📤 Upload: http://localhost:{port}/upload")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)