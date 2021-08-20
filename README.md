# Model-H: Automated Horizontal Window Opener

The Model-H is a smart window opener that uses HTTP requests to open and close your windows. Combine it with Node-RED, Home Assistant, or any other system capable of sending HTTP requests and get your window to open and close automatically.

![window opener main](/media/window-gif.gif)

## Use cases

While you can use Alexa, Google or other voice control, home automation is where this device shines. 

1. Use an indoor air quality sensor (like an Awair) to trigger the window to air out the room
2. Check Purple Air sensors hourly and close your windows when bad outdoor air is detected
2. Measure indoor and outdoor temperatures and cool your room when necessary
3. Check weather APIs if it's raining to open/close your window
4. Set a schedule to listen to the morning birds chirp

## How it works

This video has the top cover removed to help you see it better.

![window opener top](/media/top-gif.gif)

The Model-H uses a NEMA 17 stepper motor that is connected to a lead screw. A custom PCB with ESP32 and TMC2209 drives the motor. Two hall effect limit switches on each end stop the motor when it reaches the end.


## Safety features

Safety is the primary concern with this device. 

In case of emergencies, the entire device can be instantly removed for your window. (see GIF above)

![window opener main](/media/hand-gif.gif)

In case an object or limb gets in the way during window operations, the device will automatically stop and save its location. 

In the event that you leave the window locked, the device will automatically detect a locked window and stop the motor.


## Will it work on your window?

Before you get too excited and buy/build this, please be sure it will work on your window. The height of your window sill is the primary factor to consider.

### Is your window sill the correct height?

![window opener GIF](/media/window-sill.jpg)

The maximum distance from the top of the window frame to the sill is 2 inches (Red text in the image above). Any more than 2 inches and you will need to raise the window opener. One solution is to use a piece of wood such as a 1x4 or 2x4 in order to elevate the entire device.

In order to properly attach the window mount (white piece in the above photo), your window needs 14mm of the lower sash of the window to be exposed.

### Is your window wide enough?

The device is just under 22" from end to end. This means your window needs to be at least 44" wide. Also add in 2 inches to be safe. So your window needs to be 46" wide from end to end.

### Is your window too heavy?

The motor has been tested to move up to 40 lbs. However, this is extremely heavy and may cause problems. If your window is this heavy, lubricate it with dry silicone spray and check if that helps.


## How to build it

This build includes many different screws, nuts, and hardware that are difficult to find. To bring the cost of building this to the lowest possible level, we have created a kit, as well as a list of additional required hardware from Amazon. By purchasing the large and heavy products from Amazon, we can decrease the total cost of the entire build to an affordable level.

To decrease the price even more, please 3D print the parts in the "hardware" folder. If you do not have a 3D printer, you may purchase a kit with 3D printed parts.

* Total parts cost: ~$130 USD
* Total filament costs: ~$10 USD
* Total print time: ~24 hours (You can also purchase the 3D prints for $40 USD)
* Toal assembly time: ~20 minutes

Purchase these parts. Feel free to find cheaper alternatives on Amazon or elsewhere.

1.  Electronics & hardware kit

    ![window opener parts](/media/parts.jpg)

    * [**Excluding** 3D printed parts](https://valarsystems.com/products/automatic-window-opener?variant=39590892240955) ($99 USD)
    * [**Including** 3D printed parts](https://valarsystems.com/products/automatic-window-opener?variant=39590892208187) ($139 USD)

2. <a href="https://amzn.to/2XAAUiN" target="_blank">Stepper motor</a> ($10-20 USD)
    * NEMA 17
    * 60mm body (If your window needs less than 20 lbs to move, you can use a 48mm body)

3. <a href="https://amzn.to/3xVVnuL" target="_blank">Lead screw</a> ($6-10 USD)
    * T8 Trapezoidal
    * 400mm length

**Power Supply:** Be sure to note how long your cord needs to be. Please purchase #5 below for a nicer build. ($9-23 USD)

4. <a href="https://amzn.to/3xVVnuL" target="_blank">Power Supply Option 1</a> 
    * 12V  
    * 3A+
    * 2.5mm x 5.5mm barrel connector size
    * Center positive pin

5. Use these parts for a cleaner build. You can customize the length of the power wire which is also much thinner and easier to hide.
    1. <a href="https://amzn.to/3k75ist" target="_blank">Power Supply Option 2</a>
    2. <a href="https://amzn.to/2VV82S1" target="_blank">Barrel Adapter</a>
    3. <a href="https://amzn.to/3CTFUz3" target="_blank">22/2 Wire</a>


## How to 3D print it

Your window might open **from** the left **to** the right, or it might open **from** the right **to** the left.

The only version available is the ability to open from right to left. The other version will be added later.

Go to the repo folder "hardware" -> "Plastics" -> "open-left" -> "platters"

These PrusaSlicer platters are set up to print. Otherwise just print the STLs individually (not recommended because print orientation is critical). 

### Print Settings:
* Use PETG **only**
* 0.25 mm layer height
* In PrusaSlicer go to "Print Settings" -> "Seam position" -> set to "Rear"


## How to install it

Installation is **super easy**. Total install time is just a few minutes. Attach 2 mounts, wait 24 hours for the adhesives to build some strength, and start using.

![window opener mount](/media/mount-gif.gif)

There are 2 mounts that are attached with adhesive. If necessary, you can also use a screw into the sill, but that has been required. 

First attach the window mount.

Next, attach the sill mount.

Wait 24 hours for the adhesives to set and you can now use the window opener.


## Sending commands

Commands are sent via HTTP requests

Follow the instructions outlined in the ![firmware](/firmware) folder.


## Node-RED workflow

Use Node-RED in Home Assistant to automate everything. Click the image below to watch a YouTube video on how it works.

[![Youtube Link](/media/node-red-flow.jpg)](https://youtu.be/ou7uRED_ff0)
