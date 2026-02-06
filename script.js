class MapaFotos {
    constructor() {
        this.baseURL = window.location.origin;
        this.map = null;
        this.markers = [];
        this.fotos = [];
        this.trajetosKML = [];
        this.kmlLayers = [];
        this.markerLayer = null;
        
        console.log('🗺️ Iniciando Mapa de Fotos...');
        console.log('Base URL:', this.baseURL);
        
        this.init();
    }
    
    async init() {
        try {
            // 1. Inicializar mapa IMEDIATAMENTE
            this.initMap();
            
            // 2. Configurar interface
            this.setupUI();
            
            // 3. Carregar dados
            await this.carregarDados();
            
            console.log('✅ Mapa inicializado com sucesso!');
            
        } catch (error) {
            console.error('❌ Erro na inicialização:', error);
            this.mostrarErro('Erro ao inicializar o mapa: ' + error.message);
        }
    }
    
    initMap() {
        console.log('Inicializando mapa Leaflet...');
        
        // Verificar se o elemento #map existe
        const mapElement = document.getElementById('map');
        if (!mapElement) {
            throw new Error('Elemento #map não encontrado no HTML');
        }
        
        // Criar mapa (centro no Brasil)
        this.map = L.map('map').setView([-15.7942, -47.8822], 4);
        
        // Adicionar tiles do OpenStreetMap
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }).addTo(this.map);
        
        // Criar layer group para marcadores
        this.markerLayer = L.layerGroup().addTo(this.map);
        
        console.log('✅ Mapa Leaflet inicializado');
    }
    
    setupUI() {
        console.log('Configurando interface...');
        
        // Atualizar status
        const statusElement = document.getElementById('status');
        if (statusElement) {
            statusElement.textContent = '🔄 Carregando dados...';
            statusElement.style.color = '#3498db';
        }
        
        // Criar loader se não existir
        if (!document.getElementById('loading-overlay')) {
            const loader = document.createElement('div');
            loader.id = 'loading-overlay';
            loader.className = 'loading-overlay';
            loader.innerHTML = `
                <div class="loader"></div>
                <div class="loading-text">Carregando mapa...</div>
            `;
            document.body.appendChild(loader);
        }
        
        // Mostrar loader
        this.showLoader('Carregando dados...');
    }
    
    async carregarDados() {
        console.log('Carregando dados do servidor...');
        
        try {
            // Tentar carregar tudo de uma vez
            const response = await fetch(`${this.baseURL}/api/all`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log('Dados recebidos:', data);
            
            // Processar fotos
            this.fotos = data.fotos || [];
            console.log(`📸 ${this.fotos.length} fotos carregadas`);
            
            // Processar trajetos
            this.trajetosKML = data.trajetos || [];
            console.log(`🗺️ ${this.trajetosKML.length} trajetos carregados`);
            
            // Atualizar interface
            this.atualizarInterface();
            
            // Esconder loader
            this.hideLoader();
            
        } catch (error) {
            console.error('Erro ao carregar dados:', error);
            
            // Tentar carregar separadamente como fallback
            await this.carregarDadosFallback();
        }
    }
    
    async carregarDadosFallback() {
        console.log('Tentando carregar dados separadamente...');
        
        try {
            // Carregar fotos
            const fotosResponse = await fetch(`${this.baseURL}/api/fotos`);
            if (fotosResponse.ok) {
                this.fotos = await fotosResponse.json();
                console.log(`📸 ${this.fotos.length} fotos carregadas (fallback)`);
            }
            
            // Carregar trajetos
            const kmlResponse = await fetch(`${this.baseURL}/api/kml`);
            if (kmlResponse.ok) {
                const kmlData = await kmlResponse.json();
                this.trajetosKML = kmlData.trajetos || [];
                console.log(`🗺️ ${this.trajetosKML.length} trajetos carregados (fallback)`);
            }
            
            // Atualizar interface
            this.atualizarInterface();
            
        } catch (error) {
            console.error('Erro no fallback:', error);
            this.mostrarErro('Não foi possível carregar os dados. Tente recarregar a página.');
        } finally {
            this.hideLoader();
        }
    }
    
    atualizarInterface() {
        console.log('Atualizando interface...');
        
        // Atualizar status
        const statusElement = document.getElementById('status');
        if (statusElement) {
            const total = this.fotos.length + this.trajetosKML.length;
            statusElement.textContent = `✅ ${this.fotos.length} fotos e ${this.trajetosKML.length} trajetos carregados`;
            statusElement.style.color = '#2ecc71';
        }
        
        // Adicionar marcadores das fotos
        if (this.fotos.length > 0) {
            this.adicionarMarcadores();
        }
        
        // Adicionar trajetos KML
        if (this.trajetosKML.length > 0) {
            this.adicionarTrajetosAoMapa();
        }
        
        // Atualizar lista de fotos
        this.atualizarListaFotos();
        
        // Ajustar visão do mapa
        this.ajustarVisaoMapa();
        
        // Adicionar controles
        this.adicionarControles();
    }
    
    adicionarMarcadores() {
        console.log('Adicionando marcadores ao mapa...');
        
        // Limpar marcadores antigos
        this.markerLayer.clearLayers();
        this.markers = [];
        
        this.fotos.forEach((foto, index) => {
            // Criar ícone personalizado
            const icon = L.divIcon({
                html: `<div style="
                    background-color: #e74c3c;
                    color: white;
                    border-radius: 50%;
                    width: 35px;
                    height: 35px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 16px;
                    border: 3px solid white;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.3);
                    cursor: pointer;
                ">📷</div>`,
                className: 'custom-marker',
                iconSize: [35, 35],
                iconAnchor: [17, 35]
            });
            
            // Criar marcador
            const marker = L.marker([foto.latitude, foto.longitude], {
                icon: icon,
                title: foto.filename
            }).addTo(this.markerLayer);
            
            // Adicionar popup
            const popupContent = `
                <div style="text-align: center; padding: 10px; max-width: 250px;">
                    <img src="${foto.thumbnail || 'https://via.placeholder.com/150x150?text=Thumbnail'}" 
                         style="width: 150px; height: 150px; object-fit: cover; border-radius: 5px; margin-bottom: 10px;"
                         onerror="this.src='https://via.placeholder.com/150x150?text=Erro+carregar'">
                    <div style="font-weight: bold; margin: 5px 0;">${foto.filename}</div>
                    <div style="font-size: 12px; color: #666;">${foto.data_tirada || 'Data não disponível'}</div>
                    <button onclick="window.mapaFotos.mostrarFotoDetalhada('${foto.filename}')"
                            style="background: #3498db; color: white; border: none; padding: 8px 15px; border-radius: 4px; cursor: pointer; margin-top: 10px; width: 100%;">
                        Ver Foto
                    </button>
                </div>
            `;
            
            marker.bindPopup(popupContent);
            
            // Evento de clique
            marker.on('click', () => {
                this.mostrarDetalhesFoto(foto);
                this.destacarMarcador(marker);
            });
            
            // Guardar referência
            marker.fotoData = foto;
            this.markers.push(marker);
        });
        
        console.log(`✅ ${this.markers.length} marcadores adicionados`);
    }
    
    adicionarTrajetosAoMapa() {
        console.log('Adicionando trajetos KML...');
        
        // Limpar layers antigos
        this.kmlLayers.forEach(layer => layer.remove());
        this.kmlLayers = [];
        
        this.trajetosKML.forEach((trajeto, index) => {
            if (trajeto.type === 'LineString' && trajeto.coordinates) {
                // Criar linha
                const polyline = L.polyline(trajeto.coordinates, {
                    color: trajeto.color || '#e74c3c',
                    weight: trajeto.weight || 3,
                    opacity: trajeto.opacity || 0.7,
                    dashArray: trajeto.dashArray || '5, 5'
                }).addTo(this.map);
                
                // Adicionar popup
                if (trajeto.name) {
                    polyline.bindPopup(`
                        <div style="text-align: center; padding: 10px;">
                            <h4 style="margin: 0 0 10px 0;">${trajeto.name}</h4>
                            ${trajeto.filename ? `<p style="font-size: 12px; color: #666;">Arquivo: ${trajeto.filename}</p>` : ''}
                            <button onclick="window.mapaFotos.zoomParaTrajeto(${index})"
                                    style="background: #3498db; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer;">
                                🗺️ Centralizar
                            </button>
                        </div>
                    `);
                }
                
                this.kmlLayers.push(polyline);
            }
        });
        
        console.log(`✅ ${this.kmlLayers.length} trajetos adicionados`);
    }
    
    adicionarControles() {
        // Botão para centralizar em todas as fotos
        const control = L.Control.extend({
            onAdd: function(map) {
                const container = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
                container.innerHTML = `
                    <button style="
                        background: white;
                        border: 2px solid rgba(0,0,0,0.2);
                        border-radius: 4px;
                        padding: 8px;
                        cursor: pointer;
                        font-size: 16px;
                    " title="Centralizar em todas as fotos">📍</button>
                `;
                
                container.onclick = () => {
                    if (window.mapaFotos.markers.length > 0) {
                        const bounds = L.latLngBounds(window.mapaFotos.markers.map(m => m.getLatLng()));
                        window.mapaFotos.map.fitBounds(bounds.pad(0.1));
                    }
                };
                
                return container;
            }
        });
        
        new control({ position: 'topleft' }).addTo(this.map);
        
        // Botão para mostrar/esconder trajetos
        if (this.kmlLayers.length > 0) {
            const kmlControl = L.Control.extend({
                onAdd: function(map) {
                    const container = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
                    container.innerHTML = `
                        <button style="
                            background: #e74c3c;
                            color: white;
                            border: none;
                            border-radius: 4px;
                            padding: 8px 12px;
                            cursor: pointer;
                            font-size: 14px;
                            font-weight: bold;
                        " title="Mostrar/Esconder Trajetos">🗺️ Trajetos</button>
                    `;
                    
                    let visible = true;
                    
                    container.onclick = () => {
                        visible = !visible;
                        window.mapaFotos.kmlLayers.forEach(layer => {
                            if (visible) {
                                map.addLayer(layer);
                                container.querySelector('button').style.background = '#e74c3c';
                            } else {
                                map.removeLayer(layer);
                                container.querySelector('button').style.background = '#95a5a6';
                            }
                        });
                    };
                    
                    return container;
                }
            });
            
            new kmlControl({ position: 'topleft' }).addTo(this.map);
        }
    }
    
    mostrarDetalhesFoto(foto) {
        console.log('Mostrando detalhes da foto:', foto.filename);
        
        const container = document.getElementById('foto-container');
        const nomeArquivo = document.getElementById('nome-arquivo');
        const coordenadas = document.getElementById('coordenadas');
        const data = document.getElementById('data');
        
        if (container) {
            // URL da thumbnail (usar placeholder se não tiver)
            const thumbUrl = foto.thumbnail 
                ? `${this.baseURL}${foto.thumbnail}`
                : 'https://via.placeholder.com/300x200?text=Sem+thumbnail';
            
            container.innerHTML = `
                <img src="${thumbUrl}" 
                     alt="${foto.filename}"
                     onclick="window.mapaFotos.mostrarFotoGrande('${foto.filename}')"
                     style="cursor: pointer; max-width: 100%; border-radius: 8px;"
                     title="Clique para ver em tamanho maior">
            `;
        }
        
        if (nomeArquivo) nomeArquivo.textContent = foto.filename;
        if (coordenadas) coordenadas.textContent = `${foto.latitude.toFixed(6)}, ${foto.longitude.toFixed(6)}`;
        if (data) data.textContent = foto.data_tirada || 'Data não disponível';
        
        // Destacar na lista
        this.highlightListItem(foto.filename);
    }
    
    mostrarFotoGrande(nomeArquivo) {
        const foto = this.fotos.find(f => f.filename === nomeArquivo);
        if (!foto) return;
        
        // URL da imagem original
        const imageUrl = foto.full_image || foto.original_url;
        
        // Criar modal se não existir
        if (!document.getElementById('modal-foto')) {
            const modal = document.createElement('div');
            modal.id = 'modal-foto';
            modal.className = 'modal';
            modal.innerHTML = `
                <div class="modal-content">
                    <span class="close-modal" onclick="window.mapaFotos.fecharModal()">&times;</span>
                    <img id="modal-img" style="max-width: 90vw; max-height: 80vh;">
                </div>
            `;
            document.body.appendChild(modal);
            
            // Fechar ao clicar fora
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.fecharModal();
                }
            });
        }
        
        // Mostrar modal
        const modal = document.getElementById('modal-foto');
        const modalImg = document.getElementById('modal-img');
        
        modalImg.src = imageUrl;
        modalImg.alt = foto.filename;
        modal.style.display = 'block';
        
        // Destacar marcador
        const marker = this.markers.find(m => m.fotoData.filename === nomeArquivo);
        if (marker) {
            this.destacarMarcador(marker);
        }
    }
    
    fecharModal() {
        const modal = document.getElementById('modal-foto');
        if (modal) {
            modal.style.display = 'none';
        }
    }
    
    destacarMarcador(marker) {
        // Remover destaque anterior
        this.markers.forEach(m => {
            m.setIcon(this.getIconPadrao());
        });
        
        // Aplicar novo ícone
        marker.setIcon(this.getIconAtivo());
        
        // Abrir popup
        marker.openPopup();
        
        // Centralizar no marcador
        this.map.setView(marker.getLatLng(), Math.max(this.map.getZoom(), 12));
    }
    
    getIconPadrao() {
        return L.divIcon({
            html: `<div style="
                background-color: #e74c3c;
                color: white;
                border-radius: 50%;
                width: 35px;
                height: 35px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 16px;
                border: 3px solid white;
                box-shadow: 0 2px 5px rgba(0,0,0,0.3);
                cursor: pointer;
            ">📷</div>`,
            className: 'custom-marker',
            iconSize: [35, 35],
            iconAnchor: [17, 35]
        });
    }
    
    getIconAtivo() {
        return L.divIcon({
            html: `<div style="
                background-color: #2ecc71;
                color: white;
                border-radius: 50%;
                width: 45px;
                height: 45px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 18px;
                border: 4px solid white;
                box-shadow: 0 3px 8px rgba(0,0,0,0.4);
                cursor: pointer;
                animation: pulse 1s infinite;
            ">📷</div>
            <style>
                @keyframes pulse {
                    0% { transform: scale(1); }
                    50% { transform: scale(1.1); }
                    100% { transform: scale(1); }
                }
            </style>`,
            className: 'custom-marker-active',
            iconSize: [45, 45],
            iconAnchor: [22, 45]
        });
    }
    
    zoomParaTrajeto(index) {
        if (this.trajetosKML[index] && this.trajetosKML[index].coordinates) {
            const bounds = L.latLngBounds(this.trajetosKML[index].coordinates);
            this.map.fitBounds(bounds.pad(0.1));
        }
    }
    
    atualizarListaFotos() {
        const container = document.getElementById('lista-container');
        if (!container) return;
        
        container.innerHTML = '';
        
        if (this.fotos.length === 0) {
            container.innerHTML = '<p style="text-align: center; color: #666; padding: 20px;">Nenhuma foto carregada</p>';
            return;
        }
        
        this.fotos.forEach(foto => {
            const item = document.createElement('div');
            item.className = 'foto-item';
            item.dataset.filename = foto.filename;
            
            // URL da thumbnail
            const thumbUrl = foto.thumbnail 
                ? `${this.baseURL}${foto.thumbnail}`
                : 'https://via.placeholder.com/50x50?text=...';
            
            item.innerHTML = `
                <img src="${thumbUrl}" 
                     alt="${foto.filename}"
                     onerror="this.src='https://via.placeholder.com/50x50?text=...'"
                     style="width: 50px; height: 50px; object-fit: cover; border-radius: 5px; margin-right: 10px;">
                <div class="foto-info">
                    <div class="filename">${foto.filename.length > 20 ? foto.filename.substring(0, 20) + '...' : foto.filename}</div>
                    <div style="font-size: 12px; color: #666;">Lat: ${foto.latitude.toFixed(4)}</div>
                    <div style="font-size: 12px; color: #666;">Lng: ${foto.longitude.toFixed(4)}</div>
                </div>
            `;
            
            // Evento de clique
            item.addEventListener('click', () => {
                this.mostrarDetalhesFoto(foto);
                
                // Destacar marcador
                const marker = this.markers.find(m => m.fotoData.filename === foto.filename);
                if (marker) {
                    this.destacarMarcador(marker);
                }
            });
            
            container.appendChild(item);
        });
    }
    
    highlightListItem(filename) {
        // Remover destaque de todos
        document.querySelectorAll('.foto-item').forEach(item => {
            item.classList.remove('active');
        });
        
        // Destacar item correspondente
        const item = document.querySelector(`.foto-item[data-filename="${filename}"]`);
        if (item) {
            item.classList.add('active');
            
            // Scroll para o item
            item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }
    
    ajustarVisaoMapa() {
        if (this.markers.length === 0 && this.kmlLayers.length === 0) return;
        
        // Coletar todos os pontos
        const allPoints = [];
        
        // Pontos dos marcadores
        this.markers.forEach(marker => {
            allPoints.push(marker.getLatLng());
        });
        
        // Pontos dos trajetos
        this.trajetosKML.forEach(trajeto => {
            if (trajeto.coordinates) {
                trajeto.coordinates.forEach(coord => {
                    allPoints.push(coord);
                });
            }
        });
        
        if (allPoints.length > 0) {
            const bounds = L.latLngBounds(allPoints);
            this.map.fitBounds(bounds.pad(0.1));
        }
    }
    
    showLoader(message) {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.add('active');
            const text = overlay.querySelector('.loading-text');
            if (text && message) {
                text.textContent = message;
            }
        }
    }
    
    hideLoader() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.remove('active');
        }
    }
    
    mostrarErro(mensagem) {
        console.error('Erro:', mensagem);
        
        // Atualizar status
        const statusElement = document.getElementById('status');
        if (statusElement) {
            statusElement.textContent = `❌ ${mensagem}`;
            statusElement.style.color = '#e74c3c';
        }
        
        // Esconder loader
        this.hideLoader();
        
        // Mostrar alerta
        alert(`Erro: ${mensagem}\n\nVerifique o console para mais detalhes.`);
    }
    
    // Métodos públicos para acesso global
    mostrarFotoDetalhada(nomeArquivo) {
        this.mostrarFotoGrande(nomeArquivo);
    }
}

// Inicializar quando a página carregar
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM carregado, inicializando mapa...');
    
    try {
        window.mapaFotos = new MapaFotos();
    } catch (error) {
        console.error('Erro fatal ao inicializar:', error);
        
        const statusElement = document.getElementById('status');
        if (statusElement) {
            statusElement.textContent = `❌ Erro crítico: ${error.message}`;
            statusElement.style.color = '#e74c3c';
        }
        
        alert(`Erro crítico ao inicializar o mapa:\n${error.message}\n\nVerifique o console para detalhes.`);
    }
});