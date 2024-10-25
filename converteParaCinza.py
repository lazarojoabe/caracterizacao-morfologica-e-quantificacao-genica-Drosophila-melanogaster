import cv2

img = cv2.imread("Cg_+_Myd88488_dorsal_647_BB_04_04_14_3h.lif_Series001_z0_ch00.tif", cv2.IMREAD_GRAYSCALE)

cv2.imwrite("img-grayscale.tif", img)