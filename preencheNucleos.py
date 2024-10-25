import os
import cv2

def fillNuclei(source_dir, dest_dir):
    for file_name in os.listdir(source_dir):
        file_path = os.path.join(source_dir, file_name)
        img = cv2.imread(file_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        contours, _ = cv2.findContours(gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        
        for contour in contours:
            cv2.drawContours(img, [contour], 0, (0, 255, 0), thickness=cv2.FILLED)
        
        cv2.imwrite(os.path.join(dest_dir, f"{file_name}"), img)

nucleiEdges = "nucleos_bordas_desenhadas"
filledNuclei = "nucleos_preenchidos"

fillNuclei(nucleiEdges, filledNuclei)