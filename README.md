#Caracterização morfológica e quantificação da expressão
gênica em imagens sagitais da Drosophila melanogaster

Nesse repositório estão os materiais usados e desenvolvidos na minha iniciação científica, realizada na Universidade Federal de Uberlândia.

Em síntese, o propósito do trabalho é, dadas duas imagens – sendo uma contendo
os núcleos e a outra, suas respectivas proteínas –, detectar a expressão gênica de cada
elemento. Essa tarefa foi alcançada tomando os seguintes passos:
• Primeiramente, dada uma imagem de núcleos, o programa procura entre o DataSet
de imagens de proteínas aquela que contém a expressão gênica desses núcleos em
questão.

• Em seguida, ambas as imagens são convertidas de RGB para escala de cinza, visando
otimizar o processamento computacional. Nesse caso, como são utilizados 8 bits de
profundidade, ao converter para escala de cinza, é possível representar 256 níveis de
intensidade. Assim, essas variam entre 0 e 255.

• Após isso, é necessário binarizar a imagem de núcleos. Para essa tarefa, é aplicado
um filtro Gaussiano para a redução de ruídos e o algoritmo de Otsu, com o fito de
encontrar o threshold ótimo. Assim, é obtido uma imagem binária, isto é, contendo
somente dois tons: preto e branco.

• Vale salientar que foi experimentado utilizar o operador de Sobel para essa tarefa,
entretanto os resultados obtidos não foram satisfatórios. Desse modo, optou-se a
utilizar o método proposto por Canny, que utiliza do operador de Sobel em seus
passos.

• Com as bordas jé detectadas, fez-se o uso das funções findContours e drawCon-
tours para localizar os pontos das arestas, obtendo assim as suas coordenadas. Após
isso, essas mesmas ferramentas são utilizadas nos pontos internos a esses contornos,
preenchendo os núcleos.

• Tendo obtido acesso aos pixels de cada núcleo, é feito uma pesquisa de intensidade
na imagem de proteínas (em escala de cinza) usando as coordenadas desses pixels.
Simultaneamente em que são obtidos os valores de intensidade presentes nas proteí-
nas (que quantificam a expressão gênica), eles são adicionados a uma estrutura de
dados individual de cada imagem analisada.

• Ao fim, é possível verificar a intensidade em que a proteína foi expressa em cada
núcleo.

• Para servir de métrica geral, foi tomada a média aritmética da intensidade de pro-
teína expressa em cada imagem.
