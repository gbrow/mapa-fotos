import os
import exifread
import requests
from flask import Flask, jsonify, send_file, send_from_directory
from flask_cors import CORS
from PIL import Image, ImageOps
import json
from io import BytesIO
import time

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Configurações
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
THUMBNAIL_FOLDER = os.path.join(BASE_DIR, 'thumbnails')
CACHE_FILE = os.path.join(BASE_DIR, 'fotos_cache.json')
URLS_FILE = os.path.join(BASE_DIR, 'urls.json')

# Criar pastas necessárias
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)

THUMBNAIL_SIZE = (300, 300)

# Lista de URLs das suas fotos (você vai configurar isso)
# Exemplo:
IMAGE_URLS = [
    # Adicione suas URLs aqui
    # "https://exemplo.com/sua-foto1.jpg",
    # "https://exemplo.com/sua-foto2.jpg",
]

def carregar_urls():
    """Carrega URLs do arquivo urls.json ou usa lista padrão"""
    try:
        if os.path.exists(URLS_FILE):
            with open(URLS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('urls', [])
    except:
        pass
    return IMAGE_URLS

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

def baixar_e_processar_imagem(url):
    """Baixa e processa uma imagem da URL"""
    try:
        print(f"📥 Processando: {url[:50]}...")
        
        # Baixar imagem
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            print(f"❌ Erro HTTP {response.status_code}")
            return None
        
        # Verificar se é imagem
        content_type = response.headers.get('content-type', '')
        if 'image' not in content_type:
            print(f"❌ Não é uma imagem: {content_type}")
            return None
        
        # Extrair nome do arquivo da URL
        filename = os.path.basename(url.split('?')[0]) or f"foto_{hash(url)}.jpg"
        
        # Ler EXIF
        img_data = BytesIO(response.content)
        img_data.seek(0)
        tags = exifread.process_file(img_data, details=False)
        
        # Extrair coordenadas
        lat, lon = extrair_coordenadas(tags)
        
        if lat is None or lon is None:
            print(f"⚠️  Sem coordenadas GPS")
            return None
        
        # Criar thumbnail local
        thumb_hash = f"thumb_{abs(hash(url))}.jpg"
        thumb_path = os.path.join(THUMBNAIL_FOLDER, thumb_hash)
        
        if not os.path.exists(thumb_path):
            img_data.seek(0)
            with Image.open(img_data) as img:
                # Corrigir orientação
                try:
                    img = ImageOps.exif_transpose(img)
                except:
                    pass
                
                # Redimensionar
                img.thumbnail(THUMBNAIL_SIZE)
                
                # Converter formato se necessário
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Salvar thumbnail
                img.save(thumb_path, 'JPEG', quality=85, optimize=True)
        
        return {
            'filename': filename,
            'original_url': url,
            'latitude': float(lat),
            'longitude': float(lon),
            'thumbnail': f'/thumbnail/{thumb_hash}',
            'full_image': url,  # Usa URL original para imagem grande
            'data_tirada': str(tags.get('EXIF DateTimeOriginal', '')),
            'processed_at': time.time()
        }
        
    except requests.exceptions.Timeout:
        print(f"⏰ Timeout ao baixar imagem")
        return None
    except requests.exceptions.RequestException as e:
        print(f"🌐 Erro de rede: {e}")
        return None
    except Exception as e:
        print(f"❌ Erro ao processar imagem: {e}")
        return None

def processar_todas_fotos():
    """Processa todas as fotos das URLs"""
    print("🔄 Iniciando processamento de fotos...")
    
    urls = carregar_urls()
    if not urls:
        print("⚠️  Nenhuma URL configurada. Use a página de admin para adicionar URLs.")
        return []
    
    print(f"🔗 Total de URLs: {len(urls)}")
    
    fotos_processadas = []
    sucesso = 0
    falha = 0
    
    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] Processando...")
        
        foto_data = baixar_e_processar_imagem(url)
        
        if foto_data:
            fotos_processadas.append(foto_data)
            sucesso += 1
            print(f"✅ Sucesso: {foto_data['filename']}")
        else:
            falha += 1
    
    # Salvar cache
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(fotos_processadas, f, ensure_ascii=False, indent=2)
    
    print(f"\n🎉 Processamento concluído!")
    print(f"✅ Sucesso: {sucesso}")
    print(f"❌ Falha: {falha}")
    print(f"📊 Total no cache: {len(fotos_processadas)}")
    
    return fotos_processadas

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

@app.route('/api/fotos')
def listar_fotos():
    """Retorna lista de fotos processadas"""
    try:
        # Verificar se cache existe e é recente (menos de 1 hora)
        if os.path.exists(CACHE_FILE):
            cache_age = time.time() - os.path.getmtime(CACHE_FILE)
            if cache_age < 3600:  # 1 hora
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    fotos = json.load(f)
                    print(f"📊 Retornando {len(fotos)} fotos do cache")
                    return jsonify(fotos)
    except Exception as e:
        print(f"❌ Erro ao ler cache: {e}")
    
    # Se cache expirou ou não existe, processar novamente
    return jsonify(processar_todas_fotos())

@app.route('/thumbnail/<nome_arquivo>')
def servir_thumbnail(nome_arquivo):
    """Serve thumbnail local"""
    caminho = os.path.join(THUMBNAIL_FOLDER, nome_arquivo)
    if os.path.exists(caminho):
        return send_file(caminho, mimetype='image/jpeg')
    
    # Thumbnail padrão se não existir
    return send_from_directory('.', 'placeholder.jpg') if os.path.exists('placeholder.jpg') else 'Thumbnail não encontrada', 404

@app.route('/api/refresh')
def refresh_fotos():
    """Força atualização das fotos"""
    fotos = processar_todas_fotos()
    return jsonify({
        'success': True, 
        'message': f'Fotos atualizadas: {len(fotos)} processadas',
        'count': len(fotos)
    })

@app.route('/api/status')
def status():
    """Status do sistema"""
    urls = carregar_urls()
    cache_exists = os.path.exists(CACHE_FILE)
    cache_age = 0
    foto_count = 0
    
    if cache_exists:
        cache_age = time.time() - os.path.getmtime(CACHE_FILE)
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                foto_count = len(json.load(f))
        except:
            pass
    
    return jsonify({
        'urls_configured': len(urls),
        'cache_exists': cache_exists,
        'cache_age_minutes': int(cache_age / 60) if cache_age else 0,
        'fotos_in_cache': foto_count,
        'thumbnails_count': len(os.listdir(THUMBNAIL_FOLDER)) if os.path.exists(THUMBNAIL_FOLDER) else 0
    })

# Página de ADMIN para gerenciar URLs
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    """Página administrativa para gerenciar URLs"""
    if request.method == 'POST':
        urls = request.form.get('urls', '')
        urls_list = [url.strip() for url in urls.split('\n') if url.strip()]
        
        # Salvar em arquivo
        with open(URLS_FILE, 'w', encoding='utf-8') as f:
            json.dump({'urls': urls_list}, f, indent=2)
        
        return '''
            <html>
            <body style="font-family: Arial; padding: 30px;">
                <h1>✅ URLs salvas com sucesso!</h1>
                <p>Total: {} URLs</p>
                <p><a href="/api/refresh">Clique aqui para processar as novas fotos</a></p>
                <br>
                <a href="/admin">↩️ Voltar ao admin</a> | 
                <a href="/">🗺️ Ver mapa</a>
            </body>
            </html>
        '''.format(len(urls_list))
    
    # Carregar URLs existentes
    urls = carregar_urls()
    urls_text = '\n'.join(urls)
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin - Mapa de Fotos</title>
        <style>
            body {{ 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                padding: 30px;
                max-width: 1000px;
                margin: 0 auto;
                background: #f5f5f5;
            }}
            
            .container {{
                background: white;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            
            h1 {{ color: #333; margin-bottom: 5px; }}
            .subtitle {{ color: #666; margin-bottom: 30px; }}
            
            .card {{
                background: #f8f9fa;
                padding: 20px;
                border-radius: 8px;
                margin: 20px 0;
                border-left: 4px solid #3498db;
            }}
            
            textarea {{
                width: 100%;
                height: 300px;
                padding: 15px;
                border: 2px solid #ddd;
                border-radius: 5px;
                font-family: monospace;
                font-size: 14px;
            }}
            
            button {{
                background: #3498db;
                color: white;
                border: none;
                padding: 12px 25px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
                margin: 10px 5px;
            }}
            
            button:hover {{ background: #2980b9; }}
            
            .btn-success {{ background: #2ecc71; }}
            .btn-success:hover {{ background: #27ae60; }}
            
            .btn-warning {{ background: #f39c12; }}
            .btn-warning:hover {{ background: #d68910; }}
            
            .info {{ 
                background: #e8f4fc; 
                padding: 15px; 
                border-radius: 5px;
                margin: 15px 0;
            }}
            
            .status-info {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin: 20px 0;
            }}
            
            .stat-card {{
                background: white;
                padding: 15px;
                border-radius: 8px;
                text-align: center;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }}
            
            .stat-value {{
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
            }}
            
            .stat-label {{
                font-size: 14px;
                color: #7f8c8d;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>⚙️ Painel Administrativo</h1>
            <p class="subtitle">Gerencie as URLs das fotos do mapa</p>
            
            <div class="status-info" id="status-info">
                <!-- Status será carregado por JavaScript -->
            </div>
            
            <div class="card">
                <h3>🔗 URLs das Fotos</h3>
                <p>Adicione uma URL por linha. As URLs devem ser públicas e acessíveis.</p>
                
                <form method="POST">
                    <textarea name="urls" placeholder="https://exemplo.com/foto1.jpg
https://exemplo.com/foto2.jpg
https://exemplo.com/foto3.jpg">{urls_text}</textarea>
                    
                    <div style="margin-top: 20px;">
                        <button type="submit" class="btn-success">💾 Salvar URLs</button>
                        <button type="button" onclick="testarURLs()" class="btn-warning">🧪 Testar URLs</button>
                        <button type="button" onclick="atualizarFotos()">🔄 Processar Fotos</button>
                        <a href="/" style="margin-left: 20px; color: #3498db;">🗺️ Ver Mapa</a>
                    </div>
                </form>
            </div>
            
            <div class="info">
                <h4>💡 Formato das URLs:</h4>
                <ul>
                    <li>Devem ser URLs públicas diretamente para imagens</li>
                    <li>Formatos suportados: JPG, JPEG, PNG</li>
                    <li>As fotos devem ter metadados EXIF com coordenadas GPS</li>
                    <li>Exemplos válidos:</li>
                    <ul>
                        <li><code>https://raw.githubusercontent.com/usuario/repo/main/foto.jpg</code></li>
                        <li><code>https://drive.google.com/uc?export=download&id=FILE_ID</code> (Google Drive)</li>
                        <li><code>https://seusite.com/fotos/viagem.jpg</code></li>
                    </ul>
                </ul>
            </div>
            
            <div class="card">
                <h3>🛠️ Ferramentas</h3>
                <div>
                    <button onclick="limparCache()">🗑️ Limpar Cache</button>
                    <button onclick="limparThumbnails()">🖼️ Limpar Thumbnails</button>
                    <button onclick="verLogs()">📋 Ver Logs</button>
                </div>
            </div>
        </div>
        
        <script>
            // Carregar status
            function carregarStatus() {{
                fetch('/api/status')
                    .then(r => r.json())
                    .then(data => {{
                        document.getElementById('status-info').innerHTML = `
                            <div class="stat-card">
                                <div class="stat-value">${{data.urls_configured || 0}}</div>
                                <div class="stat-label">URLs Configuradas</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-value">${{data.fotos_in_cache || 0}}</div>
                                <div class="stat-label">Fotos no Cache</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-value">${{data.thumbnails_count || 0}}</div>
                                <div class="stat-label">Thumbnails</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-value">${{data.cache_age_minutes || 0}}m</div>
                                <div class="stat-label">Idade do Cache</div>
                            </div>
                        `;
                    }});
            }}
            
            // Atualizar fotos
            function atualizarFotos() {{
                if (confirm('Isso irá reprocessar todas as fotos. Continuar?')) {{
                    fetch('/api/refresh')
                        .then(r => r.json())
                        .then(data => {{
                            alert(`✅ ${{data.message}}`);
                            carregarStatus();
                        }});
                }}
            }}
            
            // Testar URLs
            function testarURLs() {{
                const urls = document.querySelector('textarea[name="urls"]').value;
                const urlList = urls.split('\\n').filter(u => u.trim());
                
                if (urlList.length === 0) {{
                    alert('Adicione URLs para testar');
                    return;
                }}
                
                alert(`🔍 Testando ${{urlList.length}} URLs...\\n\\nA primeira URL será testada agora.`);
                
                // Testar primeira URL
                const primeiraUrl = urlList[0];
                window.open(primeiraUrl, '_blank');
            }}
            
            // Limpar cache
            function limparCache() {{
                if (confirm('Tem certeza que deseja limpar o cache?')) {{
                    fetch('/api/refresh?_clean=1')
                        .then(() => {{
                            alert('Cache limpo!');
                            carregarStatus();
                        }});
                }}
            }}
            
            // Limpar thumbnails
            function limparThumbnails() {{
                if (confirm('Isso irá apagar todas as thumbnails. Continuar?')) {{
                    fetch('/api/clear-thumbs')
                        .then(r => r.json())
                        .then(data => {{
                            alert(data.message);
                            carregarStatus();
                        }})
                        .catch(() => alert('Função não disponível'));
                }}
            }}
            
            // Inicializar
            carregarStatus();
            setInterval(carregarStatus, 30000); // Atualizar a cada 30 segundos
        </script>
    </body>
    </html>
    '''