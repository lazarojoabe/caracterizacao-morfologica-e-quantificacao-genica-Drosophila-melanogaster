import cv2
import os
import numpy as np
def getContoursCoord(contours):
    coordinates = []
    for contour in contours:
        for point in contour:
            coordinates.append(tuple(point[0]))  # Adiciona as coordenadas (x, y)
    return coordinates  

def searchIntensities(proteinImg, coordinates):
    intensities = []
    for coord in coordinates:
        x, y = coord
        intensity = proteinImg[y, x]
        intensities.append(intensity)
    return intensities



nuclei = os.listdir("nucleos_preenchidos")
proteins = os.listdir("imagens_proteinas")

for file in nuclei:
    caminho_origem = os.path.join("nucleos_preenchidos", file)
    img = cv2.imread(caminho_origem, cv2.IMREAD_GRAYSCALE)
    #grayNuclei = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
    # Verificar se há uma imagem de proteína correspondente
    for proteinImg in proteins:
        #o que muda de uma imagem de núcleo para uma de proteína é o final; "z0_ch00.tif" é de núcleo
        #e "_z0_ch02.tif" é de proteína
        if proteinImg == file.replace("_z0_ch00.tif", "_z0_ch02.tif"):
            caminho_proteina = os.path.join("imagens_proteinas", proteinImg)
            img_proteina = cv2.imread(caminho_proteina, cv2.IMREAD_GRAYSCALE)
            #proteina_gray = cv2.cvtColor(img_proteina, cv2.COLOR_BGR2GRAY)
            coordinates = getContoursCoord(contours)
            qtdMediaProteina = searchIntensities(img_proteina, coordinates)
            print(f"Valor medio de proteina na imagem {file} eh {np.mean(qtdMediaProteina)}")

