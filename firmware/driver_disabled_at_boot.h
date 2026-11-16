#pragma once
// The driver starts disabled at boot.
//
// This object's constructor runs before app_main, ahead of ESPHome's setup. It
// drives the TMC2209 ENN pin (active low) high, which disables the driver. The
// level is set before the pin becomes an output, so it never drives low. ESPHome's
// pin setup keeps the level; TMC2209Stepper::setup() then writes VACTUAL 0 and
// enables the driver.
//
// GC_DRIVER_ENN_GPIO comes from the build flags (glasscalibur.yaml, pin_enn).
// gpio_set_level and gpio_set_direction are register writes that don't log on
// success, so they can run this early.
#include "driver/gpio.h"

namespace glasscalibur {

struct DriverDisabledAtBoot {
  DriverDisabledAtBoot() {
    gpio_set_level(static_cast<gpio_num_t>(GC_DRIVER_ENN_GPIO), 1);
    gpio_set_direction(static_cast<gpio_num_t>(GC_DRIVER_ENN_GPIO), GPIO_MODE_OUTPUT);
  }
};

static DriverDisabledAtBoot driver_disabled_at_boot;

}  // namespace glasscalibur
