import cv2
import mediapipe as mp
import pyautogui

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

hands = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.7)
cap = cv2.VideoCapture(0)

screen_width, screen_height = pyautogui.size()
mouse_pressed = False  # estado do clique

def is_clicking(hand_landmarks):
    """
    Retorna True se os dedos médio, anelar e mindinho estiverem fechados.
    Indicador fica livre para controlar o mouse.
    """
    fingers_to_check = [
        (12, 10), # Médio
        (16, 14), # Anelar
        (20, 18)  # Mindinho
    ]

    closed = 0
    for tip, pip in fingers_to_check:
        if hand_landmarks.landmark[tip].y > hand_landmarks.landmark[pip].y:
            closed += 1

    return closed == 3  # todos os 3 dobrados


while True:
    ret, frame = cap.read()
    if not ret:
        break

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb_frame)

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            # Pega coordenada do indicador
            x = hand_landmarks.landmark[8].x * screen_width
            y = hand_landmarks.landmark[8].y * screen_height

            # Move o mouse com o indicador
            pyautogui.moveTo(x, y)

            # Verifica se é gesto de clique (outros dedos fechados)
            if is_clicking(hand_landmarks):
                if not mouse_pressed:
                    pyautogui.mouseDown()
                    mouse_pressed = True
            else:
                if mouse_pressed:
                    pyautogui.mouseUp()
                    mouse_pressed = False

            # Desenha a mão (debug)
            mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

    cv2.imshow("Hand Tracking", frame)

    if cv2.waitKey(1) & 0xFF == 27:  # ESC para sair
        break

cap.release()
cv2.destroyAllWindows()
