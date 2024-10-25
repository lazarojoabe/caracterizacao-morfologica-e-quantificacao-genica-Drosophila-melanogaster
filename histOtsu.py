import cv2
import numpy as np
import matplotlib.pyplot as plt

# Carregar a imagem
img = cv2.imread('imgTeste.tif')

# Separar os canais
blue, _, _ = cv2.split(img)

histograma = cv2.calcHist([blue], [0], None, [256], [0, 256])

# Criar uma imagem em branco para desenhar o histograma
altura = 400
largura = 512
hist_img = np.zeros((altura, largura), dtype=np.uint8)

# Normalizar o histograma para se ajustar à altura da imagem
cv2.normalize(histograma, histograma, alpha=0, beta=altura, norm_type=cv2.NORM_MINMAX)

# Desenhar o histograma
for i in range(1, 256):
    cv2.line(hist_img, (i - 1, altura - int(histograma[i - 1])),
             (i, altura - int(histograma[i])), 255, 2)

# Salvar a imagem do histograma
cv2.imwrite('histograma_cv.png', hist_img)

# Exibir a imagem e o histograma
plt.figure(figsize=(12, 5))

# Exibir a imagem original
plt.subplot(1, 2, 1)
plt.imshow(blue, cmap='gray')
plt.title('Imagem em Escala de Cinza')
plt.axis('off')

# Exibir o histograma com Matplotlib
plt.subplot(1, 2, 2)
plt.imshow(hist_img, cmap='gray')
plt.title('Histograma em Barras')
plt.axis('off')

plt.tight_layout()
plt.show()