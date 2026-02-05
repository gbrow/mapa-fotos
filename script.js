class MapaFotos {
    constructor() {
        this.baseURL = window.location.origin;
        this.map = null;
        this.markers = [];
        this.fotos = [];
        this.currentMarker = null;
        this.currentFoto = null;
        
        console.log('🗺️ Iniciando Mapa de Fotos...');
        this.init();
    }
    
    async init() {
        // Inicializar mapa primeiro
        this.initMap();
        
        // Configurar modal
        this.setupModal();
        
        // Carregar fotos
        await this.carregarFotos();
        
        // Adicionar eventos de teclado
        this.addKeyboardEvents();
    }
    
    initMap() {
        // Criar mapa
        this.map = L.map('map').setView([-15.7942, -47.8822], 4);
        
        // Adicionar mapa base
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap',
            maxZoom: 19
        }).addTo(this.map);
        
        console.log('✅ Mapa inicializado');
    }
    
    setupModal() {
        const modal = document.getElementById('modal');
        const closeBtn = document.querySelector('.close');
        const modalImg = document.getElementById('modal-img');
        const modalCaption = document.getElementById('modal-caption');
        
        // Configurar fechamento
        closeBtn.onclick = () => this.fecharModal();
        
        modal.onclick = (e) => {
            if (e.target === modal) {
                this.fecharModal();
            }
        };
        
        // Permitir navegação na imagem com arrastar
        let isDragging = false;
        let startX, startY, scrollLeft, scrollTop;
        
        modalImg.addEventListener('mousedown', (e) => {
            if (modalImg.naturalWidth > modalImg.clientWidth || 
                modalImg.naturalHeight > modalImg.clientHeight) {
                isDragging = true;
                modalImg.style.cursor = 'grabbing';
                
                startX = e.pageX - modalImg.offsetLeft;
                startY = e.pageY - modalImg.offsetTop;
                scrollLeft = modalImg.scrollLeft;
                scrollTop = modalImg.scrollTop;
                
                e.preventDefault();
            }
        });
        
        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            
            const x = e.pageX - modalImg.offsetLeft;
            const y = e.pageY - modalImg.offsetTop;
            const walkX = (x - startX) * 2;
            const walkY = (y - startY) * 2;
            
            modalImg.scrollLeft = scrollLeft - walkX;
            modalImg.scrollTop = scrollTop - walkY;
        });
        
        document.addEventListener('mouseup', () => {
            isDragging = false;
            modalImg.style.cursor = 'grab';
        });
        
        // Zoom com rodinha do mouse
        modalImg.addEventListener('wheel', (e) => {
            if (e.ctrlKey) {
                e.preventDefault();
                const rect = modalImg.getBoundingClientRect();
                const mouseX = e.clientX - rect.left;
                const mouseY = e.clientY - rect.top;
                
                const scaleChange = e.deltaY > 0 ? 0.9 : 1.1;
                const currentTransform = modalImg.style.transform || 'scale(1)';
                const currentScale = parseFloat(currentTransform.match(/scale\(([^)]+)\)/)?.[1] || 1);
                const newScale = Math.max(0.5, Math.min(3, currentScale * scaleChange));
                
                modalImg.style.transform = `scale(${newScale})`;
                modalImg.style.transformOrigin = `${mouseX}px ${mouseY}px`;
            }
        }, { passive: false });
        
        // Resetar zoom ao clicar duas vezes
        modalImg.addEventListener('dblclick', () => {
            modalImg.style.transform = 'scale(1)';
            modalImg.style.transformOrigin = 'center center';
        });
        
        this.modal = modal;
        this.modalImg = modalImg;
        this.modalCaption = modalCaption;
        this.closeBtn = closeBtn;
        
        // Adicionar botões de controle ao modal
        this.addModalControls();
    }
    
    addModalControls() {
        // Criar container para controles
        const controls = document.createElement('div');
        controls.className = 'modal-controls';
        controls.innerHTML = `
            <button class="modal-btn zoom-in" title="Zoom In (+)">+</button>
            <button class="modal-btn zoom-out" title="Zoom Out (-)">-</button>
            <button class="modal-btn zoom-reset" title="Resetar Zoom">↺</button>
            <button class="modal-btn prev" title="Foto Anterior (←)">◀</button>
            <button class="modal-btn next" title="Próxima Foto (→)">▶</button>
        `;
        
        this.modal.querySelector('.modal-content').appendChild(controls);
        
        // Adicionar eventos aos botões
        controls.querySelector('.zoom-in').onclick = () => this.zoomImage(1.2);
        controls.querySelector('.zoom-out').onclick = () => this.zoomImage(0.8);
        controls.querySelector('.zoom-reset').onclick = () => this.resetZoom();
        controls.querySelector('.prev').onclick = () => this.navigatePhoto(-1);
        controls.querySelector('.next').onclick = () => this.navigatePhoto(1);
    }
    
    addKeyboardEvents() {
        document.addEventListener('keydown', (e) => {
            // Só funciona se o modal estiver aberto
            if (this.modal.style.display !== 'block') return;
            
            switch(e.key) {
                case 'Escape':
                    this.fecharModal();
                    break;
                case 'ArrowLeft':
                    this.navigatePhoto(-1);
                    break;
                case 'ArrowRight':
                    this.navigatePhoto(1);
                    break;
                case '+':
                case '=':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.zoomImage(1.2);
                    }
                    break;
                case '-':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.zoomImage(0.8);
                    }
                    break;
                case '0':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.resetZoom();
                    }
                    break;
            }
        });
    }
    
    zoomImage(factor) {
        const currentTransform = this.modalImg.style.transform || 'scale(1)';
        const currentScale = parseFloat(currentTransform.match(/scale\(([^)]+)\)/)?.[1] || 1);
        const newScale = Math.max(0.5, Math.min(5, currentScale * factor));
        
        this.modalImg.style.transform = `scale(${newScale})`;
        this.modalImg.style.transformOrigin = 'center center';
        this.modalImg.style.cursor = newScale > 1 ? 'grab' : 'default';
    }
    
    resetZoom() {
        this.modalImg.style.transform = 'scale(1)';
        this.modalImg.style.transformOrigin = 'center center';
        this.modalImg.style.cursor = 'default';
    }
    
    navigatePhoto(direction) {
        if (!this.currentFoto || this.fotos.length === 0) return;
        
        const currentIndex = this.fotos.findIndex(f => f.filename === this.currentFoto.filename);
        if (currentIndex === -1) return;
        
        let newIndex = currentIndex + direction;
        
        // Circular navigation
        if (newIndex < 0) newIndex = this.fotos.length - 1;
        if (newIndex >= this.fotos.length) newIndex = 0;
        
        const newFoto = this.fotos[newIndex];
        this.mostrarFotoGrande(newFoto.filename);
    }
    
    fecharModal() {
        this.modal.style.display = 'none';
        this.resetZoom();
    }
    
    async carregarFotos() {
        const status = document.getElementById('status');
        status.textContent = '🔄 Carregando fotos...';
        
        try {
            console.log('📡 Buscando fotos da API...');
            const response = await fetch(`${this.baseURL}/api/fotos`);
            
            if (!response.ok) {
                throw new Error(`Erro: ${response.status}`);
            }
            
            this.fotos = await response.json();
            console.log(`✅ ${this.fotos.length} fotos carregadas`);
            
            if (this.fotos.length === 0) {
                status.textContent = '⚠️ Nenhuma foto com GPS encontrada';
                return;
            }
            
            status.textContent = `✅ ${this.fotos.length} fotos carregadas`;
            
            // Adicionar marcadores
            this.adicionarMarcadores();
            
            // Atualizar lista
            this.atualizarListaFotos();
            
            // Ajustar mapa
            this.ajustarVisaoMapa();
            
        } catch (error) {
            console.error('❌ Erro:', error);
            status.textContent = '❌ Erro ao carregar fotos';
        }
    }
    
    adicionarMarcadores() {
        // Limpar marcadores antigos
        this.markers.forEach(m => m.remove());
        this.markers = [];
        
        this.fotos.forEach(foto => {
            // Criar marcador
            const marker = L.marker([foto.latitude, foto.longitude], {
                title: foto.filename,
                icon: this.criarIcone()
            }).addTo(this.map);
            
            // Adicionar popup
            const popupContent = `
                <div style="text-align: center; padding: 5px; max-width: 200px;">
                    <img src="${this.baseURL}${foto.thumbnail}" 
                         style="width: 120px; height: 120px; object-fit: cover; border-radius: 4px; margin-bottom: 5px;">
                    <div style="font-weight: bold; margin: 5px 0; font-size: 12px;">${foto.filename}</div>
                    <button onclick="mapaFotos.mostrarFoto('${foto.filename}')"
                            style="background: #667eea; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 11px;">
                        Ver Foto
                    </button>
                </div>
            `;
            
            marker.bindPopup(popupContent);
            
            // Evento de clique
            marker.on('click', () => {
                this.mostrarDetalhesFoto(foto);
                this.destacarMarcador(marker);
                this.highlightListItem(foto.filename);
            });
            
            marker.fotoData = foto;
            this.markers.push(marker);
        });
    }
    
    criarIcone() {
        return L.divIcon({
            html: `<div style="
                background-color: #ff4757;
                color: white;
                border-radius: 50%;
                width: 32px;
                height: 32px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 16px;
                border: 3px solid white;
                box-shadow: 0 2px 5px rgba(0,0,0,0.3);
                cursor: pointer;
            ">📷</div>`,
            className: 'custom-icon',
            iconSize: [32, 32],
            iconAnchor: [16, 32]
        });
    }
    
    mostrarDetalhesFoto(foto) {
        this.currentFoto = foto;
        
        const container = document.getElementById('foto-container');
        const nomeArquivo = document.getElementById('nome-arquivo');
        const coordenadas = document.getElementById('coordenadas');
        const data = document.getElementById('data');
        
        // Imagem
        const imgUrl = `${this.baseURL}${foto.thumbnail}`;
        container.innerHTML = `
            <img src="${imgUrl}" 
                 alt="${foto.filename}"
                 onclick="mapaFotos.mostrarFotoGrande('${foto.filename}')"
                 style="cursor: pointer;"
                 title="Clique para ampliar"
                 onerror="this.src='https://via.placeholder.com/300x200?text=Erro+carregar+imagem'">
        `;
        
        // Detalhes
        nomeArquivo.textContent = foto.filename;
        coordenadas.textContent = `${foto.latitude.toFixed(6)}, ${foto.longitude.toFixed(6)}`;
        data.textContent = foto.data_tirada || 'Data não disponível';
        
        // Destacar item na lista
        this.highlightListItem(foto.filename);
    }
    
    mostrarFotoGrande(nomeArquivo) {
        const foto = this.fotos.find(f => f.filename === nomeArquivo);
        if (!foto) return;
        
        this.currentFoto = foto;
        this.modalImg.src = `${foto.full_image}`;
        this.modalImg.alt = foto.filename;
        this.modalImg.style.cursor = 'grab';
        
        this.modalCaption.textContent = `${foto.filename} (${foto.latitude.toFixed(6)}, ${foto.longitude.toFixed(6)})`;
        
        this.modal.style.display = 'block';
        
        // Resetar zoom
        this.resetZoom();
        
        // Destacar marcador
        const marker = this.markers.find(m => m.fotoData.filename === nomeArquivo);
        if (marker) {
            this.destacarMarcador(marker);
        }
        
        // Destacar item na lista
        this.highlightListItem(foto.filename);
    }
    
    mostrarFoto(nomeArquivo) {
        this.mostrarFotoGrande(nomeArquivo);
    }
    
    destacarMarcador(marker) {
        // Remover destaque anterior
        if (this.currentMarker) {
            this.currentMarker.setIcon(this.criarIcone());
        }
        
        // Criar ícone destacado
        const iconAtivo = L.divIcon({
            html: `<div style="
                background-color: #2ed573;
                color: white;
                border-radius: 50%;
                width: 40px;
                height: 40px;
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
            className: 'custom-icon-active',
            iconSize: [40, 40],
            iconAnchor: [20, 40]
        });
        
        marker.setIcon(iconAtivo);
        this.currentMarker = marker;
        
        // Abrir popup e centralizar
        marker.openPopup();
        this.map.setView(marker.getLatLng(), Math.max(this.map.getZoom(), 12));
    }
    
    atualizarListaFotos() {
        const container = document.getElementById('lista-container');
        container.innerHTML = '';
        
        this.fotos.forEach(foto => {
            const item = document.createElement('div');
            item.className = 'foto-item';
            item.dataset.filename = foto.filename;
            
            item.innerHTML = `
                <img src="${this.baseURL}${foto.thumbnail}" 
                     alt="${foto.filename}"
                     onerror="this.src='https://via.placeholder.com/40?text=...'">
                <div class="foto-info">
                    <div class="filename">${foto.filename.length > 20 ? foto.filename.substring(0, 20) + '...' : foto.filename}</div>
                    <div>Lat: ${foto.latitude.toFixed(4)}</div>
                    <div>Lng: ${foto.longitude.toFixed(4)}</div>
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
            
            // Eventos de hover
            item.addEventListener('mouseenter', () => {
                if (!item.classList.contains('active')) {
                    item.classList.add('hover');
                }
            });
            
            item.addEventListener('mouseleave', () => {
                item.classList.remove('hover');
            });
            
            container.appendChild(item);
        });
    }
    
    highlightListItem(filename) {
        // Remover classes active de todos os itens
        document.querySelectorAll('.foto-item').forEach(item => {
            item.classList.remove('active', 'hover');
        });
        
        // Adicionar classe active ao item correspondente
        const item = document.querySelector(`.foto-item[data-filename="${filename}"]`);
        if (item) {
            item.classList.add('active');
            item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }
    
    ajustarVisaoMapa() {
        if (this.markers.length === 0) return;
        
        const bounds = L.latLngBounds(this.markers.map(m => m.getLatLng()));
        this.map.fitBounds(bounds.pad(0.1));
    }
}

// Inicializar quando a página carregar
document.addEventListener('DOMContentLoaded', () => {
    window.mapaFotos = new MapaFotos();
});