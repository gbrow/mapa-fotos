import os
import exifread
from flask import Flask, jsonify, send_file, render_template_string
from flask_cors import CORS
from PIL import Image, ImageOps
import json

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Configurações
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FOTOS_FOLDER = os.path.join(BASE_DIR, 'fotos')
THUMBNAIL_FOLDER = os.path.join(BASE_DIR, 'thumbnails')
CACHE_FILE = os.path.join(BASE_DIR, 'fotos_cache.json')

# Criar pastas necessárias
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
        print(f"⚠️  Crie a pasta 'fotos' e coloque suas fotos nela!")
        return fotos_data
    
    arquivos = os.listdir(FOTOS_FOLDER)
    print(f"📁 Encontrados {len(arquivos)} arquivos na pasta 'fotos'")
    
    for filename in arquivos:
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            caminho_completo = os.path.join(FOTOS_FOLDER, filename)
            
            try:
                print(f"📸 Processando: {filename}")
                
                with open(caminho_completo, 'rb') as f:
                    tags = exifread.process_file(f, details=False)
                
                latitude, longitude = extrair_coordenadas(tags)
                
                if latitude is not None and longitude is not None:
                    print(f"   ✅ Coordenadas: {latitude:.6f}, {longitude:.6f}")
                    
                    thumbnail_path = os.path.join(THUMBNAIL_FOLDER, filename)
                    
                    if not os.path.exists(thumbnail_path):
                        try:
                            with Image.open(caminho_completo) as img:
                                img = ImageOps.exif_transpose(img)
                                img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                                
                                if img.mode in ('RGBA', 'LA', 'P'):
                                    img = img.convert('RGB')
                                
                                img.save(thumbnail_path, 'JPEG', optimize=True, quality=85)
                                print(f"   ✅ Thumbnail criada")
                        except Exception as e:
                            print(f"   ❌ Erro thumbnail: {e}")
                            continue
                    
                    fotos_data.append({
                        'filename': filename,
                        'latitude': float(latitude),
                        'longitude': float(longitude),
                        'thumbnail': f'/thumbnail/{filename}',
                        'full_image': f'/foto/{filename}',
                        'data_tirada': str(tags.get('EXIF DateTimeOriginal', '')) if 'EXIF DateTimeOriginal' in tags else None
                    })
                else:
                    print(f"   ❌ Sem coordenadas GPS")
                    
            except Exception as e:
                print(f"❌ Erro processando {filename}: {e}")
    
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(fotos_data, f, ensure_ascii=False, indent=2)
    
    print(f"🎉 Processamento concluído: {len(fotos_data)} fotos com coordenadas")
    return fotos_data

@app.route('/')
def index():
    """Página principal"""
    return app.send_static_file('index.html')

@app.route('/api/fotos')
def listar_fotos():
    """API para listar fotos"""
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
    except:
        pass
    
    return jsonify(processar_fotos())

@app.route('/foto/<nome_arquivo>')
def servir_foto(nome_arquivo):
    """Serve foto original"""
    caminho = os.path.join(FOTOS_FOLDER, nome_arquivo)
    if os.path.exists(caminho):
        return send_file(caminho, mimetype='image/jpeg')
    return 'Foto não encontrada', 404

@app.route('/thumbnail/<nome_arquivo>')
def servir_thumbnail(nome_arquivo):
    """Serve thumbnail"""
    caminho = os.path.join(THUMBNAIL_FOLDER, nome_arquivo)
    if os.path.exists(caminho):
        return send_file(caminho, mimetype='image/jpeg')
    
    caminho_original = os.path.join(FOTOS_FOLDER, nome_arquivo)
    if os.path.exists(caminho_original):
        return send_file(caminho_original, mimetype='image/jpeg')
    
    return 'Thumbnail não encontrada', 404

@app.route('/debug')
def debug():
    """Página de debug"""
    info = {
        'fotos_folder': FOTOS_FOLDER,
        'fotos_existem': os.path.exists(FOTOS_FOLDER),
        'fotos_qtd': len(os.listdir(FOTOS_FOLDER)) if os.path.exists(FOTOS_FOLDER) else 0,
        'thumbnails_qtd': len(os.listdir(THUMBNAIL_FOLDER)) if os.path.exists(THUMBNAIL_FOLDER) else 0
    }
    return jsonify(info)

if __name__ == '__main__':
    print("=" * 60)
    print("🗺️  MAPA DE FOTOS COM COORDENADAS GPS")
    print("=" * 60)
    print(f"📂 Pasta de fotos: {FOTOS_FOLDER}")
    
    if not os.path.exists(FOTOS_FOLDER):
        print(f"\n⚠️  ATENÇÃO: Pasta 'fotos' não existe!")
        print(f"👉 Crie a pasta: {FOTOS_FOLDER}")
        print("👉 Coloque suas fotos dentro dela\n")
        os.makedirs(FOTOS_FOLDER, exist_ok=True)
    
    # Processar fotos
    processar_fotos()
    
    print("\n🚀 Servidor iniciando...")
    print("🌐 Acesse: http://localhost:5000")
    print("🐛 Debug: http://localhost:5000/debug")
    print("=" * 60)
    
    app.run(debug=True, port=5000, host='0.0.0.0')