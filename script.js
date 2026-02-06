class MapaFotos {
    constructor() {
        this.baseURL = window.location.origin;
        this.map = null;
        this.markers = [];
        this.fotos = [];
        this.trajetosKML = [];
        this.kmlLayers = [];
        
        console.log('🗺️ Iniciando Mapa de Fotos...');
        this.init();
    }
    
    async init() {
        // Inicializar mapa
        this.initMap();
        
        // Carregar dados
        await this.carregarDados();
        
        // Atualizar interface
        this.atualizarStatus();
    }
    
    async carregarDados() {
        this.showLoader('Carregando dados...');
        
        try {
            // Carregar fotos
            console.log('📸 Carregando fotos...');
            await this.carregarFotos();
            
            // Carregar KMLs
            console.log('🗺️ Carregando trajetos...');
            await this.carregarTrajetosKML();
            
        } catch (error) {
            console.error('Erro:', error);
            this.mostrarErro('Erro ao carregar dados');
        } finally {
            this.hideLoader();
        }
    }
    
    async carregarFotos() {
        try {
            const response = await fetch(`${this.baseURL}/api/fotos`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            this.fotos = await response.json();
            console.log(`✅ ${this.fotos.length} fotos carregadas`);
            
            if (this.fotos.length > 0) {
                this.adicionarMarcadores();
                this.atualizarListaFotos();
                this.ajustarVisaoMapa();
            }
            
        } catch (error) {
            console.error('Erro ao carregar fotos:', error);
            // Tentar carregar tudo junto
            await this.carregarTudoJunto();
        }
    }
    
    async carregarTrajetosKML() {
        try {
            const response = await fetch(`${this.baseURL}/api/kml`);
            
            if (response.ok) {
                const data = await response.json();
                this.trajetosKML = data.trajetos || [];
                
                if (this.trajetosKML.length > 0) {
                    this.adicionarTrajetosAoMapa();
                    console.log(`✅ ${this.trajetosKML.length} trajeto(s) carregado(s)`);
                }
            }
        } catch (error) {
            console.error('Erro ao carregar KML:', error);
        }
    }
    
    async carregarTudoJunto() {
        try {
            const response = await fetch(`${this.baseURL}/api/all`);
            
            if (response.ok) {
                const data = await response.json();
                this.fotos = data.fotos || [];
                this.trajetosKML = data.trajetos || [];
                
                console.log(`📊 Dados carregados: ${this.fotos.length} fotos, ${this.trajetosKML.length} trajetos`);
                
                if (this.fotos.length > 0) {
                    this.adicionarMarcadores();
                    this.atualizarListaFotos();
                    this.ajustarVisaoMapa();
                }
                
                if (this.trajetosKML.length > 0) {
                    this.adicionarTrajetosAoMapa();
                }
            }
        } catch (error) {
            console.error('Erro ao carregar tudo:', error);
        }
    }
    
    // ... resto das funções do mapa (manter as existentes) ...
}