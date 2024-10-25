import cv2
import os

def applyGaussian(source_dir, dest_dir):
    for file_name in os.listdir(source_dir):
        file_path = os.path.join(source_dir, file_name)
        img = cv2.imread(file_path)
        blue, _, _ = cv2.split(img)

        #img = cv2.cvtColor(blue, cv2.COLOR_BGR2GRAY)

        gaussian = cv2.GaussianBlur(blue, (5, 5), 1)

        cv2.imwrite(os.path.join(dest_dir, f"{file_name}"), gaussian)

def applyOtsu(source_dir, dest_dir):
    for file_name in os.listdir(source_dir):
        file_path = os.path.join(source_dir, file_name)
        img = cv2.imread(file_path)
        blue, _, _ = cv2.split(img)

        #img = cv2.cvtColor(blue, cv2.COLOR_BGR2GRAY)
        _, binary_image = cv2.threshold(blue, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        cv2.imwrite(os.path.join(dest_dir, f"{file_name}"), binary_image)

        
nucleiSource = "imagens_nucleos"
nucleiGaussian = "nucleos_gaussianos"
nucleiBinaryImg = "nucleos_binarizados"

proteinSource = "imagens_proteinas"
proteinGaussian = "proteinas_gaussianas"
proteinBinaryImg = "proteinas_binarizadas"

applyGaussian(nucleiSource, nucleiGaussian)
applyOtsu(nucleiGaussian, nucleiBinaryImg)

applyGaussian(proteinSource, proteinGaussian)
applyOtsu(proteinGaussian, proteinBinaryImg)