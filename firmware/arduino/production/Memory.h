bool stalled_motor = false;
bool stop_motor = false;
volatile bool sensor1_trip = false;
volatile bool sensor2_trip = false;
int current_position;
int max_steps;
int current;
int stall; 
int accel = 10000;
int max_speed = 30000;
int tcools = (3089838.00*pow(float(max_speed),-1.00161534))*1.5; //*64 after max speed
int move_to_step = 0;
int move_to_percent = 0;
int calibrate = 0; // Set to 1 to set home position
bool run_motor = false;
int wifi_set;
bool wifi_button = false;;
String ssid;
String pass;
volatile int stall_cal;
volatile int current_cal;
int close_pos = 0;

String MYTIMEZONE;
int close_timer = 0;
int close_hour;
int close_hour_input;
int close_minute;
int open_timer = 0;
int open_hour;
int open_hour_input;
int open_minute;
String open_time_string;
String close_time_string;
int openEvent;
int closeEvent;
int openEventNow;
int closeEventNow;
int open_direction;

int open_am_pm;
String open_am_pm_s;
  
int close_am_pm;
String close_am_pm_s;

float gear_ratio = 1;
float inches_mm = 25.4;
int motor_microsteps = 64; 
int motor_steps_per_rev = 200;
int thread_pitch = 2;
int starts = 4;
int one_inch = (gear_ratio * ((motor_steps_per_rev * 1)/(thread_pitch * starts)) * inches_mm) * motor_microsteps;

int button1Timer;
int button2Timer;
int waitButton1Timer;
int waitButton2Timer;
bool motorRunning;
bool motor_running = false;

int brightness0 = 0;    // how bright the LED is
int brightness1 = 0;    // how bright the LED is
int fade0Amount = 15;    // how many points to fade the LED by
int fade1Amount = 15; 

int btn1Press;
int btn2Press;

Preferences preferences;
  
void load_preferences(){
  
  Serial.println("LOADING PREFERENCES");

  wifi_set = preferences.getInt("wifi_set", 0);
  ssid = preferences.getString ("ssid", "NO_SSID");
  pass = preferences.getString ("pass", "NO_PASSWORD");
  max_steps = preferences.getInt("max_steps", 300000);
  current = preferences.getLong("current", 1000);
  stall = preferences.getInt("stall", 10);

  open_timer = preferences.getInt("open_timer", 0);
  close_timer = preferences.getInt("close_timer", 0);
  open_hour = preferences.getInt("open_hour", 12);
  open_hour_input = preferences.getInt("open_hour_in", 12);

  open_am_pm = preferences.getInt("open_am_pm", 0);
  open_am_pm_s = preferences.getString("open_am_pm_s", "AM");

  close_hour = preferences.getInt("close_hour", 12);
  close_hour_input = preferences.getInt("close_hour_in", 12);

  open_minute = preferences.getInt("open_minute", 0);
  close_minute = preferences.getInt("close_minute", 0);
  close_am_pm = preferences.getInt("close_am_pm", 0);
  close_am_pm_s = preferences.getString("close_am_pm_s", "AM");

  MYTIMEZONE = preferences.getString("timezone", "America/Los_Angeles");

  Serial.println("FINISHED LOADING PREFERENCES");
  }

  
