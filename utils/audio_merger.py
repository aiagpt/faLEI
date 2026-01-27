import os
from typing import List

def mesclar_audios(lista_arquivos: List[str], arquivo_saida: str) -> bool:
    """
    Mescla múltiplos arquivos MP3 em um único arquivo via concatenação binária.
    Isso remove a dependência do ffmpeg, já que os arquivos do Google TTS 
    têm o mesmo formato/codec.
    
    Args:
        lista_arquivos: Lista de caminhos dos arquivos MP3
        arquivo_saida: Caminho do arquivo de saída
    
    Returns:
        True se sucesso, False caso contrário
    """
    if not lista_arquivos:
        print("[ERRO] Nenhum arquivo para mesclar.")
        return False
    
    if len(lista_arquivos) == 1:
        if lista_arquivos[0] != arquivo_saida:
            if os.path.exists(arquivo_saida):
                os.remove(arquivo_saida)
            os.rename(lista_arquivos[0], arquivo_saida)
        return True
    
    try:
        print(f"\n--- MESCLANDO {len(lista_arquivos)} ARQUIVOS DE ÁUDIO (MÉTODO NATIVO) ---")
        
        with open(arquivo_saida, 'wb') as outfile:
            for i, arquivo in enumerate(lista_arquivos, 1):
                # print(f"Adicionando parte {i}/{len(lista_arquivos)}...")
                with open(arquivo, 'rb') as infile:
                    outfile.write(infile.read())
                
                # Manter arquivos temporários conforme solicitado
                # try:
                #     os.remove(arquivo)
                # except OSError:
                #     pass
        
        print(f"Áudio mesclado salvo em: {arquivo_saida}")
        return True
        
    except Exception as e:
        print(f"[ERRO] Falha ao mesclar áudios: {e}")
        return False
