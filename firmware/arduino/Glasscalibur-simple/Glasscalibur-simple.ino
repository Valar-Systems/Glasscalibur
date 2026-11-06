/****LIBRARIES REQUIRED******
* TMCStepper: https://github.com/teemuatlut/TMCStepper
* ESP32_Button: https://github.com/esp-arduino-libs/ESP32_Button
*/

#include <TMCStepper.h>
#include <Button.h>

#define ENABLE_PIN 8
#define RX_PIN 0
#define TX_PIN 1
#define STALLGUARD_PIN 14
#define INDEX_PIN 6
#define LIMIT_1_PIN GPIO_NUM_15
#define LIMIT_2_PIN GPIO_NUM_3
#define BUTTON_PIN GPIO_NUM_23

#define R_SENSE 0.22f     // R_SENSE for current calc.
#define DRIVER_ADDRESS 0  // TMC2209 Driver address according to MS1 and MS2

// ## Speed
// Sets the speed in microsteps per second.
// If for example the the motor_microsteps is set to 16 and your stepper motor has 200 full steps per revolution (Most common type. The motor angle will be 1.8 degrees on the datasheet)
// It means 200 x 16 = 3200 steps per revolution. To set the speed to rotate one revolution per seconds, we would set the value below to 3200.
// µstep velocity v[Hz] = VACTUAL[2209] * 0.715Hz
//Change these values to get different speeds
#define CLOSE_VELOCITY 1000
#define OPEN_VELOCITY -1000
#define STOP_MOTOR_VELOCITY 0

bool stalled_motor = false;
bool motor_moving = false;
bool is_moving = false;
bool is_closing = false;
bool move_to_max = false;

uint32_t target_position;
int32_t motor_position;
uint32_t maximum_motor_position;
uint8_t target_percent;

// We communicate with the TMC2209 over UART
// But the Arduino UNO only has one Serial port which is connected to the Serial Monitor
// We can use software serial on the UNO, and hardware serial on the ESP32 or Mega 2560

TMC2209Stepper driver(&Serial1, R_SENSE, DRIVER_ADDRESS);

// Interrupt
// This interrupt will fire when a HIGH rising signal is detected on the DIAG pin. This indicates a stall.

void IRAM_ATTR stalled_position() {
  stalled_motor = true;
}

// ## Track Steps
// When using the pulse generator, the TMC2209 will tell us each time a step has been taken by pulsing the INDEX pin. We can create a tracker to add or subract steps from the tracker
// The index output gives one pulse per electrical rotation, i.e., one pulse per each four fullsteps. I
// The is_closing variable keeps track of which direction the motor is spinning, this way we know whether to add or subract from the position.

void IRAM_ATTR index_interrupt(void) {

  if (is_closing == true) {
    motor_position++;
  } else {
    motor_position--;
  }

  // Ensure motor position stays within bounds
  if (motor_position < 0) {
    motor_position = 0;
  } else if (motor_position > maximum_motor_position) {
    motor_position = maximum_motor_position;
  }
}


void IRAM_ATTR limit_1_pressed() {
  stalled_motor = true;
}

void IRAM_ATTR limit_1_pressed() {
  stalled_motor = true;
}
// Turns the motor in one direction
static void limit1SingleClickCb(void *button_handle, void *usr_data) {
  Serial.println("Limit 1 single click");
  driver.VACTUAL(OPEN_VELOCITY);
}

// Turns the motor in a different direction
static void limit2SingleClickCb(void *button_handle, void *usr_data) {
  Serial.println("Limit 2 single click");
  driver.VACTUAL(CLOSE_VELOCITY);
}

// Test the WiFi Reset Button
static void btn1SingleClickCb(void *button_handle, void *usr_data) {
  Serial.println("Button Pressed");
}


void setup() {
  Serial.begin(115200);
  Serial1.begin(115200, SERIAL_8N1, RX_PIN, TX_PIN);  // ESP32 can use any pins to Serial

  Serial.println("START setup");
  pinMode(ENABLE_PIN, OUTPUT);

  pinMode(STALLGUARD_PIN, INPUT);
  pinMode(INDEX_PIN, INPUT);

  attachInterrupt(digitalPinToInterrupt(STALLGUARD_PIN), stalled_position, RISING);
  attachInterrupt(digitalPinToInterrupt(INDEX_PIN), index_interrupt, RISING);

  Button limit1 = Button(LIMIT_1_PIN, false);
  Button limit2 = Button(LIMIT_2_PIN, false);
  Button btn1 = Button(BUTTON_PIN, false);

  limit1.attachPressDownEventCb(&limit1SingleClickCb, NULL); // Attaches button function btn1SingleClickCb
  limit2.attachPressDownEventCb(&limit2SingleClickCb, NULL); // Attaches button function btn2SingleClickCb
  btn1.attachPressDownEventCb(&btn1SingleClickCb, NULL); // Attaches button function btn2SingleClickCb

  driver.begin();  // Start all the UART communications functions behind the scenes

  /* General Registers */
  driver.I_scale_analog(false);
  driver.internal_Rsense(false);
  driver.en_spreadCycle(false);
  driver.index_otpw(false);
  driver.index_step(true);
  driver.pdn_disable(true);
  driver.mstep_reg_select(true);
  driver.multistep_filt(true);

  // NODECONF Registers
  driver.senddelay(6);

  // Factory Registers
  driver.ottrim(0);

  // Velocity Dependent Control
  driver.irun(5);  // Max current. Based on 0.11 Rsense resistors
  driver.ihold(0);
  driver.iholddelay(1);  // Set I_HOLD_DELAY to 1 to 15 for smooth standstill current decay
  driver.TPOWERDOWN(20);
  driver.TPWMTHRS(0);
  driver.VACTUAL(0);

  // CHOPCONF – Chopper Configuration
  driver.diss2vs(0);
  driver.diss2g(0);
  driver.dedge(0);
  driver.intpol(1);

  driver.mres(8);  // 8 = FULLSTEP mode. 200 pulses per revolution.
  driver.vsense(0);
  driver.tbl(2);
  driver.hend(0);
  driver.hstrt(4);
  driver.toff(5);

  // PWMCONF – Voltage PWM Mode StealthChop
  driver.pwm_lim(12);
  driver.pwm_reg(8);    // Try 2
  driver.freewheel(1);  // 1= Freewheel mode. 3 = Coil Short HS. Only short the coil when motor is NOT moving. Use for physical security
  driver.pwm_autograd(1);
  driver.pwm_autoscale(1);
  driver.pwm_freq(1);
  //driver.pwm_grad(PWM_grad);  // Test different initial values. Use scope.
  driver.pwm_ofs(36);

  driver.VACTUAL(CLOSE_VELOCITY); // Starts the movement

  Serial.println("END setup");
}

void loop() {

// Button actions are in the button functions

}
