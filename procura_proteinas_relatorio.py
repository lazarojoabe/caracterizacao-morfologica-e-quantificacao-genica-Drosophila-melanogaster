# import os
# import shutil

# # Caminho das pastas de origem
# proteinasOrigemPath = "proteinas_relatorio_final"
# nucleosOrigemPath = "imagens_nucleos"
# nucleosPreenchidosPath = "nucleos_preenchidos"

# nucleosDestinoPath = "nucleos_relatorio"
# preenchidosDestinoPath = "nucleos_preenchidos_para_relatorio_final"

# # Listar os arquivos nas pastas de origem
# preenchidos = os.listdir(nucleosPreenchidosPath)
# originais = os.listdir(nucleosOrigemPath)
# proteinas = os.listdir(proteinasOrigemPath)

# # Processar os arquivos preenchidos
# for proteina in proteinas:
#     # Copiar núcleos
#     for original in originais:
#         if(original.replace("ch00.tif", "ch02.tif") == proteina):
#             caminho_completo_nucleo = os.path.join(nucleosOrigemPath, original)
#             shutil.copy(caminho_completo_nucleo, nucleosDestinoPath)
#             print(f"Núcleo copiado: {original}")

#     # Copiar proteínas correspondentes
#     for preenchido in preenchidos:
#         if(proteina == preenchido.replace("ch00.tif", "ch02.tif")):
#             caminho_completo_preenchido = os.path.join(nucleosPreenchidosPath, preenchido)
#             shutil.copy(caminho_completo_preenchido, preenchidosDestinoPath)
#             print(f"Núcleo copiado: {preenchido}")

# print("Processo concluído.")

import os
import shutil

# Caminho das pastas de origem
proteinasOrigemPath = "proteinas_relatorio_final"
nucleosOrigemPath = "imagens_nucleos"
nucleosPreenchidosPath = "nucleos_preenchidos"

nucleosDestinoPath = "nucleos_relatorio"
preenchidosDestinoPath = "nucleos_preenchidos_para_relatorio_final"
proteinasDestinoPath = "proteinas_relatorio"
# Listar os arquivos nas pastas de origem
preenchidos = os.listdir(nucleosPreenchidosPath)
originais = os.listdir(nucleosOrigemPath)
proteinas = os.listdir(proteinasOrigemPath)

# Inicializar contador
i = 1

# Processar os arquivos preenchidos
for proteina in proteinas:
        # Copiar núcleos
    for original in originais:
        if original.replace("ch00.tif", "ch02.tif") == proteina:
            caminho_completo_nucleo = os.path.join(nucleosOrigemPath, original)
            novo_nome_nucleo = f"nucleo_original{i}.tif"
            destino_nucleo = os.path.join(nucleosDestinoPath, novo_nome_nucleo)
            shutil.copy(caminho_completo_nucleo, destino_nucleo)
            print(f"Núcleo copiado: {novo_nome_nucleo}")

    # Copiar proteínas correspondentes
    for preenchido in preenchidos:
        if proteina == preenchido.replace("ch00.tif", "ch02.tif"):
            caminho_completo_preenchido = os.path.join(nucleosPreenchidosPath, preenchido)
            novo_nome_preenchido = f"nucleo_preenchido{i}.tif"
            destino_preenchido = os.path.join(preenchidosDestinoPath, novo_nome_preenchido)
            shutil.copy(caminho_completo_preenchido, destino_preenchido)
            print(f"Preenchido copiado: {novo_nome_preenchido}")
    caminho_completo_proteinas = os.path.join(proteinasOrigemPath, proteina)
    novo_nome_proteina = f"proteina{i}.tif"
    destino_proteina = os.path.join(proteinasDestinoPath, novo_nome_proteina)
    shutil.copy(caminho_completo_proteinas, destino_proteina)
    i+=1

print("Processo concluído.")


