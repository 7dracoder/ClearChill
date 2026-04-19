import cv2
for i in range(4):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        print(f"video{i}: OK")
        cap.release()
    else:
        print(f"video{i}: fail")
