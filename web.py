from flask import Flask, Response, render_template, jsonify
from ultralytics import YOLO
import cv2
from urllib.request import urlopen
import numpy as np
import os
import time
import serial
import threading
import datetime

# Khởi tạo Flask app
app = Flask(__name__)

# Khởi tạo mô hình YOLO
model = YOLO("best.pt")
url = 'http://192.168.100.214/cam-hi.jpg'
FRUIT_CLASSES = {0: "cam lanh", 1: "cam hong"}

# Cấu hình lưu ảnh
save_dir = r"C:\Users\hadsk\Documents\code\python\BTL\Bai3\anhcam"
os.makedirs(save_dir, exist_ok=True)

# Biến toàn cục và lock
latest_annotated_frame = None
latest_detection = "unknown"
frame_lock = threading.Lock()
detection_lock = threading.Lock()

# Kết nối Arduino
try:
    arduino = serial.Serial(port="COM9", baudrate=115200, timeout=1)
    time.sleep(2)
    print("Connected to Arduino")
except Exception as e:
    print(f"Arduino connection error: {e}")
    arduino = None

def get_frame_from_esp():
    try:
        img_resp = urlopen(url, timeout=2)
        imgnp = np.asarray(bytearray(img_resp.read()), dtype=np.uint8)
        return cv2.imdecode(imgnp, -1)
    except Exception as e:
        print(f"Camera error: {e}")
        return None

def background_processing():
    global latest_annotated_frame, latest_detection
    while True:
        frame = get_frame_from_esp()
        if frame is not None:
            # Xử lý frame
            results = model(frame)
            annotated_frame = results[0].plot()
            
            # Cập nhật detection
            new_detection = "unknown"
            for box in results[0].boxes:
                class_id = int(box.cls[0])
                if class_id in FRUIT_CLASSES:
                    new_detection = FRUIT_CLASSES[class_id]
                    break
            
            # Cập nhật biến toàn cục
            with frame_lock:
                latest_annotated_frame = annotated_frame.copy()
            with detection_lock:
                latest_detection = new_detection
        time.sleep(0.1)

def arduino_handler():
    while True:
        if arduino and arduino.in_waiting > 0:
            try:
                raw_data = arduino.readline()
                message = raw_data.decode('utf-8', errors='replace').strip()
                
                if message == "CHECK":
                    print("\nReceived CHECK request")
                    time.sleep(1.5)
                    
                    # Chụp ảnh mới
                    frame = get_frame_from_esp()
                    if frame is None:
                        arduino.write("unknown\n".encode())
                        continue
                    
                    # Xử lý và lưu ảnh
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    original_path = os.path.join(save_dir, f"original_{timestamp}.jpg")
                    cv2.imwrite(original_path, frame)
                    
                    results = model(frame)
                    annotated_path = os.path.join(save_dir, f"annotated_{timestamp}.jpg")
                    cv2.imwrite(annotated_path, results[0].plot())
                    
                    # Gửi kết quả
                    result = "unknown"
                    for box in results[0].boxes:
                        class_id = int(box.cls[0])
                        if class_id in FRUIT_CLASSES:
                            result = FRUIT_CLASSES[class_id]
                            break
                    
                    arduino.write(f"{result}\n".encode())
                    print(f"Sent to Arduino: {result}")
                    
            except Exception as e:
                print(f"Arduino error: {e}")

# Khởi chạy các luồng
processing_thread = threading.Thread(target=background_processing)
processing_thread.daemon = True
processing_thread.start()

if arduino:
    arduino_thread = threading.Thread(target=arduino_handler)
    arduino_thread.daemon = True
    arduino_thread.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    def generate():
        while True:
            with frame_lock:
                if latest_annotated_frame is None:
                    continue
                ret, jpeg = cv2.imencode('.jpg', latest_annotated_frame)
                frame_data = jpeg.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n\r\n')
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/alert_status')
def alert_status():
    with detection_lock:
        status = "cam hong" in latest_detection
        message = "Cảnh báo: Hoa quả hỏng được phát hiện!" if status else "Không phát hiện hoa quả hỏng"
    return jsonify(alert=status, message=message)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)