TaskHandle_t CurrentCalibrationTaskHandle;
TaskHandle_t StallCalibrationTaskHandle;

void TravelDistance()
{
  printf("CALIBRATION STEP 1: SETTING MAX STEPS\n");

  sensor1_trip = false;
  sensor2_trip = false;

  //disable stallguard
  detachInterrupt(STALLGUARD);
  //esp_err_t gpio_intr_disable(gpio_num_t STALLGUARD);
  

  stepper.enableOutputs();
  driver.rms_current(1500); //current = 2000
  stepper.setAcceleration(accel);
  stepper.setMaxSpeed(max_speed); //quarter speed

  //First move to close position, in case closed, then skip
  printf("MOVE 1: CLOSING\n");
  if (digitalRead(SENSOR1)) //Only do this if sensor1 is not tripped
  {

    stepper.setAcceleration(accel);
    stepper.setMaxSpeed(max_speed); //quarter speed
    stepper.moveTo(-10000);        //close all the way

    while (stepper.currentPosition() != stepper.targetPosition())
    {
      stepper.run();
      feedTheDog();

      if (sensor1_trip == true)
      {
        printf("Tripped1\n");
        stepper.setAcceleration(2000000);
        stepper.stop(); // Stop as fast as possible: sets new target
        stepper.runToPosition();
        sensor1_trip = false;
        XACTUAL = 0;
        stepper.setCurrentPosition(XACTUAL);
        break;
      }
    }
  }

  //Now open all the way
  printf("MOVE 2: OPENING\n");
  if (digitalRead(SENSOR2)) //Only do this if sensor2 is not tripped
  {

    stepper.setAcceleration(accel);
    stepper.setMaxSpeed(max_speed); //quarter speed
    stepper.moveTo(10000);
    sensor2_trip = false;

    while (stepper.currentPosition() != stepper.targetPosition())
    {
      stepper.run();
      feedTheDog();

      if (sensor2_trip == true)
      {
        printf("Tripped2\n");
        stepper.setAcceleration(2000000);
        stepper.stop(); // Stop as fast as possible: sets new target
        stepper.runToPosition();
        sensor2_trip = false;
        max_steps = stepper.currentPosition();
        break;
      }
    }
  }

  //Now close all the way
  printf("MOVE 3: FINISHING CLOSING\n");
  if (digitalRead(SENSOR1)) //Only do this if sensor2 is not tripped
  {
    stepper.setAcceleration(accel);
    stepper.setMaxSpeed(max_speed); //quarter speed
    stepper.moveTo(-10000);
    sensor1_trip = false;

    while (stepper.currentPosition() != stepper.targetPosition())
    {
      stepper.run();
      feedTheDog();

      if (sensor1_trip == true)
      {
        printf("Tripped1: MOVE 3\n");
        stepper.setAcceleration(2000000);
        stepper.stop(); // Stop as fast as possible: sets new target
        stepper.runToPosition();
        sensor1_trip = false;
        XACTUAL = 0;
        stepper.setCurrentPosition(XACTUAL);
        break;
      }
    }
  }

  printf("Finished Setting Max Steps: %i\n", max_steps);
  stepper.disableOutputs();
  attachInterrupt(STALLGUARD, stalled_position, RISING);
  preferences.putInt ("max_steps", max_steps);
}



void CurrentCalibrationTask(void *pvParameters) // UART Current Task// Change current settings depending on location
{
(void)pvParameters;

printf("Starting Current Calibration\n");

  for (;;)

    if (digitalRead(STALLGUARD))
    {
        //stalled_motor = false;
        current_cal = current_cal + 100;
        driver.rms_current(current_cal);
        printf("New Current: %i\n", current_cal);
        vTaskDelay(40);
    }
    else
    {
    vTaskDelay(1);
    }
  }


void CalibrateCurrent() //AUTO CURRENT
{
  printf("CALIBRATION STEP 2: Setting Current: \n");

  sensor1_trip = false;
  sensor2_trip = false;
  
  //vTaskSuspend(CurrentChangeHandle);
  //vTaskSuspend(StateChangeHandle);

  stepper.setAcceleration(accel);
  stepper.setMaxSpeed(max_speed);

  current_cal = 300;
  stall_cal = 30;

  driver.rms_current(current_cal);
  driver.SGTHRS(stall_cal);

  printf("Current set to: %i\n", current_cal);
  printf("Stall set to: %i\n", stall_cal);
  
  xTaskCreatePinnedToCore(
      CurrentCalibrationTask //Change Current
      , "CurrentCalibrationTask"
      , 1024 * 4 // Stack size
      , NULL
      , 1 // Priority
      , &CurrentCalibrationTaskHandle
      , 1);

  stepper.enableOutputs();

  //Open and close 2 times to be sure.
  int i;
  for (i = 0; i < 2; i++)
  {
    //Now open all the way
    Serial.println(digitalRead(SENSOR1));
    Serial.println(digitalRead(SENSOR2));
    
    if (digitalRead(SENSOR2)) //Only do this if sensor2 is not tripped
    {
      printf("MOVE 1: OPENING\n");
      stepper.setAcceleration(accel);
      stepper.setMaxSpeed(max_speed); //quarter speed
      stepper.setCurrentPosition(0);
      stepper.moveTo(one_inch * 20);
      sensor2_trip = false;

      Serial.println(stepper.currentPosition());
      Serial.println(stepper.targetPosition());
      
      while (stepper.currentPosition() != stepper.targetPosition())
      {
        stepper.run();
        feedTheDog();

        if (sensor2_trip == true)
        {
          printf("Tripped2\n");
          stepper.setAcceleration(2000);
          stepper.stop(); // Stop as fast as possible: sets new target
          stepper.runToPosition();
          sensor2_trip = false;
          break;
        }
      }
      
    }

    //Now close all the way
    if (digitalRead(SENSOR1)) //Only do this if sensor1 is not tripped
    { 
      printf("MOVE 2: CLOSING\n");
      stepper.setAcceleration(accel);
      stepper.setMaxSpeed(max_speed); //quarter speed
      stepper.moveTo(-one_inch * 20);
      sensor1_trip = false;

      while (stepper.currentPosition() != stepper.targetPosition())
      {
        stepper.run();
        feedTheDog();

        if (sensor1_trip == true)
        {
          printf("Tripped1\n");
          stepper.setAcceleration(2000000);
          stepper.stop(); // Stop as fast as possible: sets new target
          stepper.runToPosition();
          sensor1_trip = false;
          break;
        }
      }
    }
  }

  current = current_cal + 100;
  stepper.disableOutputs();
  printf("current_high: %i\n", current);

  vTaskDelete(CurrentCalibrationTaskHandle);
  //vTaskSuspend(CurrentChangeHandle);
  //vTaskResume(StateChangeHandle);

  preferences.putInt ("current", current);
  printf("current_high = %d\n", current);

  }


void StallCalibrationTask(void *pvParameters) // UART Current Task// Change current settings depending on location
{
  (void)pvParameters;

  for (;;)
  {
    if (digitalRead(STALLGUARD))
    {
        stall_cal = stall_cal - 1;
        driver.SGTHRS(stall_cal);
        printf("New Stall High: %i\n", stall_cal);
        delay(40);
    }
    else
    {
        vTaskDelay(1);
    }
  }
}

void CalibrateStall() //AUTO CURRENT
{
  printf("STEP 3: Setting Stall: \n");

  //vTaskSuspend(CurrentChangeHandle);
  //vTaskSuspend(StateChangeHandle);
  
  stepper.setAcceleration(accel);
  stepper.setMaxSpeed(max_speed);

  stall_cal = 70;//100

  driver.SGTHRS(stall_cal);
  driver.rms_current(current);

  xTaskCreatePinnedToCore(
      StallCalibrationTask //Change Current
      , "StallCalibrationTask"
      , 1024 * 4// Stack size
      , NULL
      , 1 // Priority
      , &StallCalibrationTaskHandle
      , 1);

  stepper.enableOutputs();

  //Open and close 3 times to be sure.
  int i;
  for (i = 0; i < 3; i++)
  {
    //Now open all the way
    printf("MOVE 1: OPENING %i\n", i);
    if (digitalRead(SENSOR2)) //Only do this if sensor2 is not tripped
    {
      stepper.setAcceleration(accel);
      stepper.setMaxSpeed(max_speed); //quarter speed
      stepper.moveTo(one_inch * 20);
      sensor2_trip = false;

      while (stepper.currentPosition() != stepper.targetPosition())
      {
        stepper.run();
        feedTheDog();

        if (sensor2_trip == true)
        {
          printf("Tripped2\n");
          stepper.setAcceleration(2000000);
          stepper.stop(); // Stop as fast as possible: sets new target
          stepper.runToPosition();
          sensor2_trip = false;
          break;
        }
      }
    }
    //Now close all the way
    printf("MOVE 2: CLOSING\n");
    if (digitalRead(SENSOR1)) //Only do this if sensor1 is not tripped
    {
      stepper.setAcceleration(accel);
      stepper.setMaxSpeed(max_speed);
      stepper.moveTo(-one_inch * 20);
      sensor1_trip = false;

      while (stepper.currentPosition() != stepper.targetPosition())
      {
        stepper.run();
        feedTheDog();

        if (sensor1_trip == true)
        {
          printf("Tripped1\n");
          stepper.setAcceleration(2000000);
          stepper.stop(); // Stop as fast as possible: sets new target
          stepper.runToPosition();
          sensor1_trip = false;
          break;
        }
      }
    }
  }

  stall = stall_cal - 20; //Subract 10 to make it not so sensative
  stepper.disableOutputs();
  printf("stall: %i\n", stall);
  vTaskDelete(StallCalibrationTaskHandle);
  preferences.putInt ("stall", stall);
  }
