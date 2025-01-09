// LIBRARIES
#include <WiFi.h> // To enable ESP32 Wi-Fi functionality
#include <WiFiUdp.h> // To send and receive UDP packets
#include "Wire.h" // To enable I2C communication
#include <SparkFun_KX13X.h> // For KX132 accelerometer
#include <Trill.h> // For the trill capacitive sensing

// GLOBAL VARIABLES AND OBJECTS
// udp
WiFiUDP udp;
unsigned int localPort = 3030; // Local UDP port to send/receive data

// accelerometer
SparkFun_KX132_SPI kxAccel;
outputData myData;   // Struct for the accelerometer's data
int chipSelect = D6; // Chip select pin for SPI communication

// capacitive sensor
Trill trillSensor;

// Wi-Fi credentials
const char* ssid     = "Victoria de León";
const char* password = "heyheyhep";
const char* ipAddress = "172.20.10.12";

hw_timer_t *Timer0_Cfg = NULL; // Pointer for hardware timer configuration
TaskHandle_t Task2; // Handle for FreeRTOS task

long lastMsg = millis(); // timestamp of last message
long previousMillis = millis(); // timestamp for periodic operations
long interval = 30000; //interval for periodic operations (30 sec)

// Accelerometer setup parameters
float acc_samp_freq = 2000; // sampling frequency (hz)
float gap = 1/acc_samp_freq * 1000000; // gap

// Capacitive pads setup parameters
float cap_samp_freq = 80; // sampling frequency (hz)
float gap_cap = 1/cap_samp_freq * 1000000; // gap

// Timing variables
long start_time = micros(); 
long curr_time = micros(); 

// Buffers and queues for accelerometer data
#define BYTE_ARRAY_SIZE 2200
byte send_buffer[BYTE_ARRAY_SIZE];
int send_buffer_position = 0; 
#define QUEUE_LENGTH 1 // This is the maximum number of items that can be stored in the queue at any given time.
#define BACKUP_QUEUE_LENGTH 1 // This is the maximum number of items that can be stored in the queue at any given time.
QueueHandle_t byteQueue; // Define the queue handle
QueueHandle_t byteQueue_backup;

// Buffers and queues for capacitive sensor data
#define BYTE_ARRAY_SIZE_CAP 70*5
byte send_buffer_cap[BYTE_ARRAY_SIZE_CAP];
int send_buffer_position_cap = 0; 
#define QUEUE_LENGTH_CAP 5 // This is the maximum number of items that can be stored in the queue at any given time.
#define BACKUP_QUEUE_LENGTH_CAP 10 // This is the maximum number of items that can be stored in the queue at any given time.
QueueHandle_t byteQueue_cap; // Define the queue handle
QueueHandle_t byteQueue_backup_cap;

// Function declarations
void acc_sense();
void cap_sense_thread(); 

void setup() {
  // Initialize queues
  byteQueue = xQueueCreate(QUEUE_LENGTH, BYTE_ARRAY_SIZE); // main queue for accelerometer
  byteQueue_backup = xQueueCreate(BACKUP_QUEUE_LENGTH, BYTE_ARRAY_SIZE); // backup queue for accelerometer
  byteQueue_cap = xQueueCreate(QUEUE_LENGTH_CAP, BYTE_ARRAY_SIZE_CAP); // main queue for capacitive sensor
  byteQueue_backup_cap = xQueueCreate(BACKUP_QUEUE_LENGTH_CAP, BYTE_ARRAY_SIZE_CAP); // backup queue for capacitive sensor
  Serial.begin(115200);

  // Initialize SPI communication
  pinMode(chipSelect, OUTPUT);
  digitalWrite(chipSelect, HIGH);
  SPI.begin(); // Start SPI communication
  Serial.println("Welcome.");

  // Wait for the Serial monitor to be opened.
  while (!Serial)
    delay(50);
      
  // Initialize accelerometer
  /*
  if (!kxAccel.begin(chipSelect)) // try to initialize the accelerometer
  {
    Serial.println("Could not communicate with the the KX13X. Freezing.");
    while (1); // halt execution if initialization fails
  }
  Serial.println("Ready.");
  


  // Reset the chip so that old settings don't apply to new setups.
  if (kxAccel.softwareReset())
    Serial.println("Reset.");

  // Give some time for the accelerometer to reset.
  // It needs two, but give it five for good measure.
  delay(5);
  kxAccel.enableAccel(false); // disable accelerometer before configuration
  kxAccel.setRange(SFE_KX132_RANGE2G); // 16g Range
  kxAccel.enableDataEngine(); // Enables the bit that indicates data is ready.
  kxAccel.setOutputDataRate(13); // Default is 50Hz
  kxAccel.enableAccel(); // enable again
     
  float output_rate = kxAccel.getOutputDataRate(); 
  Serial.print("Output Rate:");
  Serial.println(output_rate);
  */

  //set up capacitive sensor 
  // IMPORTANT NOTE: The device won´t work if you do not put the 0x50.
  // This is related to the hardware design, where the chip was reused from a trill board.
  int ret = trillSensor.setup(Trill::TRILL_FLEX, 0x50);

	if(ret != 0) {
		Serial.println("failed to initialise trillSensor");
		Serial.print("Error code: ");
		Serial.println(ret);
	}
  Serial.println("trillSensor set succesfully");


// more information: https://learn.bela.io/using-trill/settings-and-sensitivity/
  trillSensor.setMode(Trill::RAW); // set Trill to raw data mode
  delay(10);
  trillSensor.setScanSettings(0, 13); // 3 == CSD_SLOW_SPEED, 16 bit
  delay(10);
  trillSensor.setPrescaler(2); // prescaler value
  delay(10);

  setup_wifi();

  start_time = micros(); // record the start time

  /*
  Timer0_Cfg = timerBegin(1, 80, true); 
  timerAttachInterrupt(Timer0_Cfg, &acc_sense, true);
  timerAlarmWrite(Timer0_Cfg, gap, true);
  timerAlarmEnable(Timer0_Cfg);
  */
  
  // create FreeRTOS task for capacitive sensor
  xTaskCreatePinnedToCore(
            Task2code,  /* Task function. */
            "Task2",    /* name of task. */
            10000,      /* Stack size of task */
            NULL,       /* parameter of the task */
            1,          /* priority of the task */
            &Task2,     /* Task handle to keep track of created task */
            0);         /* pin task to core 0 */    
}

// Function to handle accelerometer data collection and buffering

/*
void IRAM_ATTR acc_sense()
{
      curr_time = micros() - start_time; // calculate elapsed time since start 
      kxAccel.getAccelData(&myData);// retrieve accelerometer data for X, Y and Z axes.

      send_buffer[send_buffer_position] = byte(0); // packet header
      send_buffer[send_buffer_position+1] = byte(255);
      send_buffer[send_buffer_position+2] = byte(0);
      send_buffer[send_buffer_position+3] = byte(255);
      send_buffer[send_buffer_position+4] = byte(0);
      send_buffer[send_buffer_position+5] = byte(1); // packet type identifier
      
      // add the timestamp to the buffer, byte by byte
      for (int i = send_buffer_position+6; i <= send_buffer_position+9; ++i) {
            send_buffer[i] = (curr_time >> (8 * (i - send_buffer_position+6))) & 0xFF; // Extract each byte of the timestamp
      }

    // scale and add x, y, z axis data to the buffer, byte by byte
      int x = (myData.xData+4*9.81)*1000;
      int y = (myData.yData+4*9.81)*1000;
      int z = (myData.zData+4*9.81)*1000;
      //Serial.println(x);
      for (int i = send_buffer_position+10; i <= send_buffer_position+13; ++i) {
            send_buffer[i] = (x >> (8 * (i - send_buffer_position+10))) & 0xFF; // Add x axis data
      }
      for (int i = send_buffer_position+14; i <= send_buffer_position+17; ++i) {
            send_buffer[i] = (y >> (8 * (i - send_buffer_position+14))) & 0xFF; // Add y axis data
      }
      for (int i = send_buffer_position+18; i <= send_buffer_position+21; ++i) {
            send_buffer[i] = (z >> (8 * (i - send_buffer_position+18))) & 0xFF; // Add z axis data
      }

      send_buffer_position = send_buffer_position + 22; // move the buffer position forward
      
      if (send_buffer_position == BYTE_ARRAY_SIZE) // if the buffer is full
      {
        xQueueSendToBackFromISR(byteQueue, send_buffer, 0); // send the buffer to the queue
        send_buffer_position = 0; // reset the buffer position
      }
}
*/

void Task2code( void * pvParameters ){
  while (true){
      if ((micros() - curr_time - start_time) > gap_cap) // check if it is time to sample data
      {
        curr_time = micros() - start_time; // update the current time
        trillSensor.requestRawData(); // request raw data from the capacitive sensor
        // add a packet header for capacitive sensor data
        send_buffer_cap[send_buffer_position_cap] = byte(0);
        send_buffer_cap[send_buffer_position_cap+1] = byte(255);
        send_buffer_cap[send_buffer_position_cap+2] = byte(0);
        send_buffer_cap[send_buffer_position_cap+3] = byte(255);
        send_buffer_cap[send_buffer_position_cap+4] = byte(0);
        send_buffer_cap[send_buffer_position_cap+5] = byte(2); // packet type identifier

        // add timestamp to the buffer
        for (int i = send_buffer_position_cap+6; i <= send_buffer_position_cap+9; ++i) {
              send_buffer_cap[i] = (curr_time >> (8 * (i - send_buffer_position_cap+6))) & 0xFF; // Extract each byte of the integer
        }
        send_buffer_position_cap = send_buffer_position_cap + 10; // move the buffer position forward

        // read raw data from the capacitive sensor and store it in the buffer
        while(trillSensor.rawDataAvailable() > 0) {
          int data = trillSensor.rawDataRead();
          for (int i = send_buffer_position_cap; i <= send_buffer_position_cap+1; ++i) {
            send_buffer_cap[i] = (data >> (8 * (i - send_buffer_position_cap))) & 0xFF; // Extract each byte of the integer
          }
          send_buffer_position_cap = send_buffer_position_cap + 2;  // move the buffer position forward
        }
        
        if (send_buffer_position_cap == BYTE_ARRAY_SIZE_CAP) // if the buffer is full
            {
              xQueueSendToBack(byteQueue_cap, send_buffer_cap, 0); // send the buffer to the queue
              send_buffer_position_cap = 0; // reset the buffer position
            }
        }
    }
}

/*
// Function to handle capacitive sensor data colletion with direct interrupt. 
void IRAM_ATTR cap_sense()
{
  curr_time = micros() - start_time; // Calculate elapsed time
  Serial.println("in timer block");
  Serial.println("in timer block2");
  
  // Add a packet header for capacitive sensor data
  send_buffer_cap[send_buffer_position_cap] = byte(0);
  send_buffer_cap[send_buffer_position_cap+1] = byte(255);
  send_buffer_cap[send_buffer_position_cap+2] = byte(0);
  send_buffer_cap[send_buffer_position_cap+3] = byte(255);
  send_buffer_cap[send_buffer_position_cap+4] = byte(0);
  send_buffer_cap[send_buffer_position_cap+5] = byte(2); // packet type identifier

  send_buffer_position_cap = send_buffer_position_cap + 6; // move the buffer position forward

  // Read raw data from the capacitive sensor and store it in the buffer
	while(trillSensor.rawDataAvailable() > 0) {
		int data = trillSensor.rawDataRead();
    for (int i = send_buffer_position_cap; i <= send_buffer_position_cap+1; ++i) {
      send_buffer_cap[i] = (data >> (8 * (i - send_buffer_position_cap))) & 0xFF; // Extract each byte of the integer
    }
    send_buffer_position_cap = send_buffer_position_cap + 2; // move the buffer position forward 
	}
  
  if (send_buffer_position_cap == BYTE_ARRAY_SIZE_CAP)
      {
        xQueueSendToBackFromISR(byteQueue_cap, send_buffer_cap, 0);
        send_buffer_position_cap = 0; 
        //Serial.println("sent to buffer");
      }
}

*/

void setup_wifi() {
    Serial.println("Connecting to ");
    Serial.println(ssid);
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) 
    {
        delay(500);
        Serial.print(".");
    }
    Serial.println("");
    Serial.println("WiFi connected");
}


// MAIN LOOP FOR DATA TRANSMISSION
void loop() {  
    byte receivedData[BYTE_ARRAY_SIZE]; // buffer for accelerometer data
    byte receivedData2[BYTE_ARRAY_SIZE_CAP]; // buffer for capacitive sensor data
    BaseType_t status; // status variable for queue operations
     
      // check for accelerometer data in the main queue
      if (uxQueueMessagesWaiting(byteQueue) > 0)
      {
        status = xQueueReceive(byteQueue, receivedData, 0); // retrieve data from queue
        xQueueSendToBack(byteQueue_backup, receivedData, 0); //  backup the data
        if (status == pdPASS) {
          udp.beginPacket(ipAddress, localPort); // start a UDP packet
          udp.write(receivedData, BYTE_ARRAY_SIZE); // write accelerometer data
          udp.endPacket(); // end the packet
          udp.beginPacket(ipAddress, localPort);
          udp.write(receivedData, BYTE_ARRAY_SIZE);
          udp.endPacket();
        }
      }

      // check for backup accelerometer data
      if (uxQueueMessagesWaiting(byteQueue_backup) > 38)
      {
        status = xQueueReceive(byteQueue_backup, receivedData, 0); // retrieve data from the backup queue
        if (status == pdPASS) {
          udp.beginPacket(ipAddress, localPort);
          udp.write(receivedData, BYTE_ARRAY_SIZE);
          udp.endPacket();
        }
      }

      // check for capacitive sensor data in the main queue
      if (uxQueueMessagesWaiting(byteQueue_cap) > 0)
      {
        status = xQueueReceive(byteQueue_cap, receivedData2, 0); // retrieve data from the queue
        xQueueSendToBack(byteQueue_backup_cap, receivedData2, 0); // backup the data
        if (status == pdPASS) {
          udp.beginPacket(ipAddress, localPort);
          udp.write(receivedData2, BYTE_ARRAY_SIZE_CAP);
          udp.endPacket();
          udp.beginPacket(ipAddress, localPort);
          udp.write(receivedData2, BYTE_ARRAY_SIZE_CAP);
          udp.endPacket();
        }
      }

      // check for backup capacitive sensor data
      if (uxQueueMessagesWaiting(byteQueue_backup_cap) > 8)
      {
        status = xQueueReceive(byteQueue_backup_cap, receivedData2, 0);
        if (status == pdPASS) {
          udp.beginPacket(ipAddress, localPort);
          udp.write(receivedData2, BYTE_ARRAY_SIZE_CAP);
          udp.endPacket();
        }
      }
    delay(20);
}



