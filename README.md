Criar e ativar um ambiente virtual (recomendado)

Isso evita conflitos entre bibliotecas:

python -m venv venv


Ativar:

Windows (CMD/PowerShell):

venv\Scripts\activate

Instalar as bibliotecas necessárias

Agora sim usar o pip dentro do ambiente:

pip install opencv-python mediapipe pyautogui


📌 Explicando:
.
opencv-python → captura de vídeo e processamento de imagem.

mediapipe → reconhecimento da mão.

pyautogui → controla o mouse/teclado.



no requirements.txt tem varios arquivos, mas instalei só esses três usando o comando acima.
