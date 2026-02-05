#!/usr/bin/env python3
"""
Script simples para gerar lista de URLs a partir de nomes de arquivos.
"""

import os
import json
from pathlib import Path
from datetime import datetime

def listar_fotos(pasta):
    """Lista todas as fotos em uma pasta"""
    pasta = Path(pasta)
    
    if not pasta.exists():
        print(f"❌ Pasta não encontrada: {pasta}")
        return []
    
    extensoes = ('.jpg', '.jpeg', '.png', '.heic', '.jfif', '.gif', '.bmp', '.tiff')
    fotos = [f for f in pasta.iterdir() 
             if f.is_file() and f.suffix.lower() in extensoes]
    
    return sorted(fotos)

def gerar_template_urls(pasta_fotos, servidor="github"):
    """
    Gera um template de URLs baseado nos nomes dos arquivos.
    
    Args:
        pasta_fotos: Caminho para a pasta com fotos
        servidor: 'github', 'drive', 'custom' ou 'local'
    """
    fotos = listar_fotos(pasta_fotos)
    
    if not fotos:
        print("❌ Nenhuma foto encontrada na pasta.")
        return
    
    print(f"📁 Pasta: {pasta_fotos}")
    print(f"📸 Fotos encontradas: {len(fotos)}")
    print("-" * 60)
    
    # Mostrar algumas fotos
    print("\n📋 Amostra de fotos:")
    for i, foto in enumerate(fotos[:10], 1):
        print(f"  {i:2d}. {foto.name}")
    if len(fotos) > 10:
        print(f"  ... e mais {len(fotos) - 10} fotos")
    
    # Gerar URLs baseadas no servidor escolhido
    urls = []
    
    if servidor == "github":
        usuario = input("\n📝 Seu usuário do GitHub: ")
        repositorio = input("📝 Nome do repositório: ") or "minhas-fotos"
        
        for foto in fotos:
            url = f"https://raw.githubusercontent.com/{usuario}/{repositorio}/main/{foto.name}"
            urls.append(url)
    
    elif servidor == "drive":
        print("\n📝 Para Google Drive:")
        print("1. Faça upload das fotos para o Google Drive")
        print("2. Compartilhe cada uma como 'Qualquer pessoa com o link'")
        print("3. Cole os links abaixo quando solicitado\n")
        
        for foto in fotos:
            while True:
                url = input(f"URL para '{foto.name}': ").strip()
                if url:
                    urls.append(url)
                    break
                else:
                    print("⚠️  URL não pode ser vazia")
    
    elif servidor == "custom":
        print("\n📝 Digite o prefixo/base das URLs")
        print("Exemplo: https://meusite.com/fotos/")
        base_url = input("URL base: ").strip()
        
        if not base_url.endswith('/'):
            base_url += '/'
        
        for foto in fotos:
            urls.append(f"{base_url}{foto.name}")
    
    elif servidor == "local":
        # Para desenvolvimento local
        print("\n⚠️  Modo local - URLs funcionarão apenas no seu computador")
        for foto in fotos:
            # URL relativa para desenvolvimento
            urls.append(f"/local/{foto.name}")
    
    else:
        print("❌ Servidor desconhecido")
        return
    
    # Salvar em diferentes formatos
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 1. JSON completo
    dados_json = {
        "servidor": servidor,
        "pasta_origem": str(pasta_fotos),
        "total_fotos": len(fotos),
        "gerado_em": str(datetime.now()),
        "urls": urls
    }
    
    with open(f'urls_{timestamp}.json', 'w', encoding='utf-8') as f:
        json.dump(dados_json, f, indent=2, ensure_ascii=False)
    
    # 2. Lista simples (uma por linha)
    with open(f'urls_{timestamp}.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(urls))
    
    # 3. Formato para app.py (apenas array)
    with open('urls.json', 'w', encoding='utf-8') as f:
        json.dump({"urls": urls}, f, indent=2, ensure_ascii=False)
    
    print(f"\n🎉 Arquivos gerados com sucesso!")
    print(f"📄 urls_{timestamp}.json - Com metadados")
    print(f"📄 urls_{timestamp}.txt - Lista simples")
    print(f"📄 urls.json - Para usar no app.py")
    
    print(f"\n📊 Resumo:")
    print(f"  Total de URLs: {len(urls)}")
    print(f"  Primeira URL: {urls[0][:80]}...")
    print(f"  Última URL: {urls[-1][:80]}...")
    
    return urls

def main():
    """Função principal"""
    print("=" * 60)
    print("🔄 GERADOR DE URLs PARA MAPA DE FOTOS")
    print("=" * 60)
    
    # Configurações
    pasta = input("📁 Caminho da pasta com fotos [fotos]: ").strip() or "fotos"
    
    print("\n🌐 Escolha o servidor de hospedagem:")
    print("  1. GitHub (recomendado)")
    print("  2. Google Drive")
    print("  3. Servidor próprio")
    print("  4. Desenvolvimento local")
    
    opcao = input("\nOpção (1-4): ").strip()
    
    servidores = {
        '1': 'github',
        '2': 'drive',
        '3': 'custom',
        '4': 'local'
    }
    
    servidor = servidores.get(opcao, 'github')
    
    print(f"\n🎯 Modo selecionado: {servidor.upper()}")
    
    gerar_template_urls(pasta, servidor)

if __name__ == "__main__":
    main()