import cv2
import os
import numpy as np
def findEdges(source_dir, limiar1, limiar2, dest_dir):
    for file_name in os.listdir(source_dir):
        file_path = os.path.join(source_dir, file_name)
        img = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)

        edge = cv2.Canny(img, limiar1, limiar2)


        cv2.imwrite(os.path.join(dest_dir, f"{file_name}"), edge)

def drawContoursEdges(source_dir, dest_dir):
    for file_name in os.listdir(source_dir):
        file_path = os.path.join(source_dir, file_name)
        img = cv2.imread(file_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
         # Detecta contornos
        contours, _ = cv2.findContours(gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        # Desenha os contornos na imagem colorida
        cv2.drawContours(img, contours, -1, (0, 255, 0), 3)  
        cv2.imwrite(os.path.join(dest_dir, f"{file_name}"), img)

nucleiSource = "nucleos_binarizados"
nucleiEdges = "nucleos_bordas"

nucleiDrawnEdges = "nucleos_bordas_desenhadas"

findEdges(nucleiSource, 0, 20, nucleiEdges)
drawContoursEdges(nucleiEdges, nucleiDrawnEdges)