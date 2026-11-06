#include <Arduino.h>
#include <ESPUI.h>
#include <ezTime.h>
#include <FastAccelStepper.h>
#include <HardwareSerial.h>
#include <TMCStepper.h>
#include <SPI.h>
#include <Preferences.h>
#include <SimpleFOC.h>
#include <SimpleFOCDrivers.h>
#include "encoders/mt6835/MagneticSensorMT6835.h"
#include "Memory.h"
#include "ResetButton.h"
#include "MotorControl.h"
#include "API.h"
#include "calibration.h"
#include "ESPUI.h"


// the setup function runs once when you press reset or power the board
void setup() {

  Serial.begin(115200);
  delay(1000);
  preferences.begin("local", false);
  load_preferences();
  setup_motors();
  API();
  ESPUIsetup();


  // Now set up tasks to run independently.
  xTaskCreatePinnedToCore(
    MotorTaskCode, //Motor Task
    "MotorTask",   // A name just for humans
    1024 * 4, // This stack size can be checked & adjusted by reading the Stack Highwater
    NULL,
    3,  // Priority, with 3 (configMAX_PRIORITIES - 1) being the highest, and 0 being the lowest.
    &MotorTask, //Task Handle
    1);

  xTaskCreatePinnedToCore(
    ButtonTaskCode, //Motor Task
    "ButtonTask",   // A name just for humans
    1024 * 4, // This stack size can be checked & adjusted by reading the Stack Highwater
    NULL,
    1,  // Priority, with 3 (configMAX_PRIORITIES - 1) being the highest, and 0 being the lowest.
    &ButtonTask, //Task Handle
    0);

}

void loop()
{
  // Empty. Things are done in Tasks.

}

/*--------------------------------------------------*/
/*---------------------- Tasks ---------------------*/
/*--------------------------------------------------*/

void ButtonTaskCode(void *pvParameters)  // Motor Task
{
  (void) pvParameters;

  for (;;)
  {

    if (btn1Press == 1) {

      if (run_motor == true && move_to_step == max_steps) {
        stepper->forceStop();
        move_to_step = 0;
        stepper->moveTo(move_to_step);
      }

      else if (run_motor == true && move_to_step == 0 )
      {
        stepper->forceStop();
        delay(100);
        move_to_step = stepper->getCurrentPosition();
        stepper->moveTo(move_to_step);
      }
      else
      {
        move_to_step = 0;
        run_motor = true;
      }
    }

    if (btn2Press == 1) {

      if (run_motor == true && move_to_step == 0) {
        stepper->forceStop();
        move_to_step = max_steps;
        stepper->moveTo(move_to_step);
      }

      else if (run_motor == true && move_to_step == max_steps )
      {
        stepper->forceStop();
        delay(100);
        move_to_step = stepper->getCurrentPosition();
        stepper->moveTo(move_to_step);
      }
      else
      {
        move_to_step = max_steps;
        run_motor = true;
      }
    }

    if (run_motor == true)
    {
      int loadAngle = 255;
      int loadTrip = 0;
      delay(300); // only delay one time
      Serial.println("Starting Detection");
      while (run_motor == true)
      {

        Serial.println(driver.SG_RESULT());
        loadAngle = driver.SG_RESULT();
        if (loadAngle <= 0)
        {
          Serial.println("SG 0");
          loadTrip++;
          loadAngle = 255;
        }

        if (loadTrip >= 2)
        {

          //stalled_motor = true;
          break;
        }
      }
    }
    else
    {
      vTaskDelay(1);
    }
  }
}


void MotorTaskCode(void *pvParameters)  // Motor Task
{
  (void) pvParameters;

  for (;;)
  {
    if (run_motor == true)
    {
      Serial.println("Run Motor Function");
      move_motor();
      run_motor = false;
      stalled_motor = false; // Reset Stall flag
      ESPUI.updateLabel(positionLabel, String(int(((float)current_position / (float)max_steps) * 100)));
      Serial.println("Motor Complete");
    }
    else if (calibrate == 1)
    {
      TravelDistance();
      CalibrateCurrent();
      ESPUI.updateNumber(currentMax, current);
      CalibrateStall();
      ESPUI.updateNumber(stallMax, stall);
      calibrate = 0;
    }
    else if (close_pos == 1)
    {
      ClosePosition();
      close_pos = 0;
    }
    else if (wifi_button == true)
    {
      button_change();
      wifi_button = false;
    }
    else
    {
      vTaskDelay(1);
    }
  }
}
