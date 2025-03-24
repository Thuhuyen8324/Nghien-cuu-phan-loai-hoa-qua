#include <Servo.h>

#define FM52_1 7    // Chân cảm biến nhận diện vật thể
#define RELAY 8     // Chân điều khiển băng chuyền
#define SERVO_PIN 9 // Chân điều khiển servo

Servo myServo;

bool isProcessing = false;
bool prevFM52_1State = HIGH;  // Giả sử mặc định là HIGH
const unsigned long PYTHON_TIMEOUT = 5000; // Thời gian chờ phản hồi từ Python (ms) = 6 giây
const unsigned long CHECK_INTERVAL = 5000; // Gửi lệnh CHECK mỗi 5 giây nếu cảm biến vẫn LOW
const unsigned long CHECK_DELAY = 5000;    // Khoảng cách tối thiểu giữa các lần CHECK = 5 giây

unsigned long lastCheckTime = 0;
unsigned long lastProcessTime = 0;

void setup() {
    Serial.begin(115200);
    pinMode(FM52_1, INPUT);
    pinMode(RELAY, OUTPUT);
    myServo.attach(SERVO_PIN);
    digitalWrite(RELAY, LOW);
    myServo.write(0);
}

void loop() {
    bool currentFM52_1State = digitalRead(FM52_1);
    unsigned long currentTime = millis();

    // Nếu cảm biến chuyển từ HIGH sang LOW hoặc đã đủ 5 giây kể từ lần check cuối cùng
    if (!isProcessing && currentFM52_1State == LOW && 
        (prevFM52_1State == HIGH || (currentTime - lastCheckTime >= CHECK_INTERVAL))) {
        
        // Đảm bảo các lệnh "CHECK" cách nhau ít nhất 5 giây
        if (currentTime - lastProcessTime >= CHECK_DELAY) {
            isProcessing = true;
            Serial.println("CHECK");
            lastCheckTime = currentTime;
            lastProcessTime = currentTime;

            String result;
            bool received = false;
            unsigned long startTime = millis();

            // Chờ phản hồi từ Python trong 6 giây
            while (millis() - startTime < PYTHON_TIMEOUT) {
                if (Serial.available() > 0) {
                    result = Serial.readStringUntil('\n');
                    result.trim();
                    received = true;
                    break;
                }
                delay(10);
            }

            if (received) {
                Serial.print("Result: ");
                Serial.println(result);

                if (result == "cam lanh") {
                    digitalWrite(RELAY, HIGH);
                    delay(4000);
                    digitalWrite(RELAY, LOW);
                } else if (result == "cam hong") {
                    digitalWrite(RELAY, HIGH);
                    delay(1900);
                    digitalWrite(RELAY, LOW);
                    myServo.write(90);
                    delay(2000);
                    myServo.write(0);
                } else {
                    Serial.println("No relevant object detected; skipping processing.");
                }
            } else {
                Serial.println("Timeout: No response from Python");
            }

            isProcessing = false;
        }
    }

    prevFM52_1State = currentFM52_1State;
}
