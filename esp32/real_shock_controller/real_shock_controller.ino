#include <BLE2902.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>

struct Button {
  char name;
  int pin;
};

const char *BLE_DEVICE_NAME = "RealShockESP32";
const char *BLE_SERVICE_UUID = "6d8f0001-7f4f-4f1d-9b55-1f4a6c3f3a10";
const char *BLE_COMMAND_UUID = "6d8f0002-7f4f-4f1d-9b55-1f4a6c3f3a10";

const Button BUTTONS[] = {
  {'A', 32}, // intensity up
  {'B', 33}, // mode change. GPIO34 is input-only on ESP32.
  {'C', 25}, // intensity down
};

const int BUTTON_PRESS_MS = 26;
const int BUTTON_RELEASE_MS = 1;
const int LEVEL_MIN = 0;
const int LEVEL_MAX = 15;
const unsigned long ZERO_STALE_MS = 13000;

char command[128];
int commandLength = 0;
char bleCommand[128];
bool bleCommandReady = false;
bool bleConnected = false;
int currentLevel = -1;
int currentMode = 1;
unsigned long zeroSinceMs = 0;
bool outputActive = false;
unsigned long outputUntilMs = 0;
int activeEventId = 0;
char activeKind[20] = "none";

void queueBleCommand(const char *value) {
  int index = 0;
  while (value[index] != '\0' && value[index] != '\n' && value[index] != '\r' && index < (int)sizeof(bleCommand) - 1) {
    bleCommand[index] = value[index];
    index++;
  }
  bleCommand[index] = '\0';
  bleCommandReady = index > 0;
}

class CommandCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *characteristic) {
    String value = characteristic->getValue();
    queueBleCommand(value.c_str());
  }
};

class ServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer *server) {
    bleConnected = true;
    Serial.println("BLE connected");
  }

  void onDisconnect(BLEServer *server) {
    bleConnected = false;
    Serial.println("BLE disconnected");
    BLEDevice::startAdvertising();
  }
};

int pinForButton(char name) {
  for (int i = 0; i < 3; i++) {
    if (BUTTONS[i].name == name) {
      return BUTTONS[i].pin;
    }
  }
  return -1;
}

void pressButton(char name) {
  int pin = pinForButton(name);
  if (pin < 0) {
    Serial.print("ERR unknown button ");
    Serial.println(name);
    return;
  }
  digitalWrite(pin, HIGH);
  delay(BUTTON_PRESS_MS);
  digitalWrite(pin, LOW);
  delay(BUTTON_RELEASE_MS);
}

void holdButton(char name, int holdMs) {
  int pin = pinForButton(name);
  if (pin < 0) {
    Serial.print("ERR unknown button ");
    Serial.println(name);
    return;
  }
  if (holdMs < 1) {
    holdMs = 1;
  }
  if (holdMs > 10000) {
    holdMs = 10000;
  }
  digitalWrite(pin, HIGH);
  delay(holdMs);
  digitalWrite(pin, LOW);
}

void noteZeroIfNeeded() {
  if (currentLevel == 0) {
    zeroSinceMs = millis();
  }
}

void enterMode3() {
  pressButton('B');
  pressButton('B');
  currentMode = 3;
}

void powerOnToZeroAndMode3() {
  pressButton('A');
  currentLevel = 0;
  zeroSinceMs = millis();
  enterMode3();
}

void forceOffFromStaleZero() {
  pressButton('C');
  currentLevel = -1;
  currentMode = 1;
}

void prepareDevice() {
  if (currentLevel == 0 && millis() - zeroSinceMs >= ZERO_STALE_MS) {
    forceOffFromStaleZero();
  }
  if (currentLevel < 0) {
    powerOnToZeroAndMode3();
  }
}

void setLevel(int targetLevel) {
  targetLevel = constrain(targetLevel, LEVEL_MIN, LEVEL_MAX);
  prepareDevice();

  while (currentLevel < targetLevel) {
    pressButton('A');
    currentLevel++;
  }
  while (currentLevel > targetLevel) {
    pressButton('C');
    currentLevel--;
  }
  noteZeroIfNeeded();
}

void printStatus() {
  Serial.print("STATUS level=");
  Serial.print(currentLevel);
  Serial.print(" mode=");
  Serial.print(currentMode);
  Serial.print(" zero_age_ms=");
  Serial.println(currentLevel == 0 ? millis() - zeroSinceMs : 0);
}

void finishOutput() {
  if (!outputActive) {
    return;
  }
  outputActive = false;
  setLevel(0);
  Serial.print("OK event id=");
  Serial.println(activeEventId);
  strcpy(activeKind, "none");
}

void runEvent(const char *kind, int intensity, int durationMs, int eventId) {
  intensity = constrain(intensity, 0, LEVEL_MAX);
  durationMs = max(0, durationMs);

  if (intensity <= 0 || durationMs <= 0 || strcmp(kind, "none") == 0) {
    outputActive = false;
    setLevel(0);
    Serial.print("OK none id=");
    Serial.println(eventId);
    return;
  }

  Serial.print("RUN ");
  Serial.print(kind);
  Serial.print(" level=");
  Serial.print(intensity);
  Serial.print(" duration_ms=");
  Serial.print(durationMs);
  Serial.print(" id=");
  Serial.println(eventId);

  setLevel(intensity);
  strncpy(activeKind, kind, sizeof(activeKind) - 1);
  activeKind[sizeof(activeKind) - 1] = '\0';
  activeEventId = eventId;
  outputUntilMs = millis() + (unsigned long)durationMs;
  outputActive = true;
}

void handleCommand(char *line) {
  while (*line == ' ' || *line == '\t') {
    line++;
  }
  if (*line == '\0') {
    return;
  }

  char verb[16] = {0};
  char kind[20] = {0};
  int intensity = 0;
  int durationMs = 0;
  int eventId = 0;

  if (sscanf(line, "%15s", verb) != 1) {
    return;
  }

  if (strcmp(verb, "status") == 0) {
    printStatus();
    return;
  }
  if (strcmp(verb, "none") == 0) {
    runEvent("none", 0, 0, 0);
    return;
  }
  if (strcmp(verb, "mode3") == 0) {
    prepareDevice();
    enterMode3();
    Serial.println("OK mode3");
    return;
  }
  if (strcmp(verb, "resetstate") == 0) {
    currentLevel = -1;
    currentMode = 1;
    Serial.println("OK resetstate");
    return;
  }
  if (strcmp(verb, "button") == 0) {
    char buttonName = '\0';
    if (sscanf(line, "%15s %c", verb, &buttonName) == 2) {
      if (buttonName >= 'a' && buttonName <= 'z') {
        buttonName = buttonName - 'a' + 'A';
      }
      pressButton(buttonName);
      Serial.print("OK button ");
      Serial.println(buttonName);
    } else {
      Serial.println("ERR use: button A|B|C");
    }
    return;
  }
  if (strcmp(verb, "hold") == 0) {
    char buttonName = '\0';
    int holdMs = 0;
    if (sscanf(line, "%15s %c %d", verb, &buttonName, &holdMs) == 3) {
      if (buttonName >= 'a' && buttonName <= 'z') {
        buttonName = buttonName - 'a' + 'A';
      }
      holdButton(buttonName, holdMs);
      Serial.print("OK hold ");
      Serial.print(buttonName);
      Serial.print(" ");
      Serial.println(holdMs);
    } else {
      Serial.println("ERR use: hold A|B|C ms");
    }
    return;
  }
  if (strcmp(verb, "level") == 0) {
    if (sscanf(line, "%15s %d", verb, &intensity) == 2) {
      setLevel(intensity);
      printStatus();
    } else {
      Serial.println("ERR use: level 0..15");
    }
    return;
  }
  if (strcmp(verb, "event") == 0) {
    if (sscanf(line, "%15s %19s %d %d %d", verb, kind, &intensity, &durationMs, &eventId) >= 4) {
      runEvent(kind, intensity, durationMs, eventId);
    } else {
      Serial.println("ERR use: event kind intensity duration_ms [id]");
    }
    return;
  }

  Serial.println("ERR commands: event/status/none/level/button/hold/mode3/resetstate");
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 3; i++) {
    pinMode(BUTTONS[i].pin, OUTPUT);
    digitalWrite(BUTTONS[i].pin, LOW);
  }
  delay(600);
  powerOnToZeroAndMode3();

  BLEDevice::init(BLE_DEVICE_NAME);
  BLEServer *server = BLEDevice::createServer();
  server->setCallbacks(new ServerCallbacks());
  BLEService *service = server->createService(BLE_SERVICE_UUID);
  BLECharacteristic *commandCharacteristic = service->createCharacteristic(
    BLE_COMMAND_UUID,
    BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR
  );
  commandCharacteristic->setCallbacks(new CommandCallbacks());
  commandCharacteristic->addDescriptor(new BLE2902());
  service->start();

  BLEAdvertising *advertising = BLEDevice::getAdvertising();
  advertising->addServiceUUID(BLE_SERVICE_UUID);
  advertising->setScanResponse(true);
  advertising->setMinPreferred(0x06);
  advertising->setMinPreferred(0x12);
  BLEDevice::startAdvertising();

  Serial.println("READY RealShockESP32 BLE A=32 B=33 C=25 mode=3 level=0");
}

void loop() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (commandLength > 0) {
        command[commandLength] = '\0';
        handleCommand(command);
        commandLength = 0;
      }
    } else if (commandLength < (int)sizeof(command) - 1) {
      command[commandLength++] = c;
    }
  }

  if (bleCommandReady) {
    char localCommand[128];
    strncpy(localCommand, bleCommand, sizeof(localCommand) - 1);
    localCommand[sizeof(localCommand) - 1] = '\0';
    bleCommandReady = false;
    handleCommand(localCommand);
  }

  if (outputActive && (long)(millis() - outputUntilMs) >= 0) {
    finishOutput();
  }
}
