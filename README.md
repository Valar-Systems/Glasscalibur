# Model-H: Automated Horizontal Window Opener

The Model-H is a smart window opener that uses HTTP requests to open and close your windows. Combine it with Node-RED, Home Assistant, or any other system capable of sending HTTP requests and get your window to open and close automatically.

# Build Guides

You can find the assembly instructions and video in the [hardware folder](/hardware).

You can find the window attachment guide in the [hardware folder](/hardware).

## Use cases

While you can use Alexa, Google or other voice control, home automation is where this device shines. 

1. Use an indoor air quality sensor (like an Awair) to trigger the window to air out the room
2. Check Purple Air sensors hourly and close your windows when bad outdoor air is detected
2. Measure indoor and outdoor temperatures and cool your room when necessary
3. Check weather APIs if it's raining to open/close your window
4. Set a schedule to listen to the morning birds chirp

## How it works

![window opener main](/media/window-gif.gif)

This video has the top cover removed to help you see it better.

![window opener top](/media/top-gif.gif)

The Model-H uses a NEMA 17 stepper motor that is connected to a lead screw. A custom PCB with an ESP32 and TMC2209 drives the motor. Two hall effect sensors on each end stop the motor when it reaches the end.

![window opener top](/media/model-h-pcb.jpg)


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

To make this affordable to build, we have created a kit. Otherwise, sourcing the screws and hardware individually gets very expensive.

### Kits

There are two versions of the kit. One with plastics and one without. If you have a 3D printer, feel free to print your own.

* [Link to kit **Excluding** 3D printed parts](https://valarsystems.com/products/automatic-window-opener?variant=39590892240955) 
* [Link to kit **Including** 3D printed parts](https://valarsystems.com/products/automatic-window-opener?variant=39590892208187) 
    
![window opener GIF](/media/window-kit.jpg)

## How to 3D print it

Your window might open **from** the left **to** the right, or it might open **from** the right **to** the left.

The only version available is the ability to open from right to left. The other version will be added later.

Go to the repo folder "hardware" -> "Plastics" -> "open-left" -> "platters"

These PrusaSlicer platters are set up to print. Otherwise just print the STLs individually (not recommended because print orientation is critical). 


## How to install it

Installation is **super easy**. Total install time is just a few minutes. Attach 2 mounts, wait 24 hours for the adhesives to build some strength, and start using.

![window opener mount](/media/mount-gif.gif)

There are 2 mounts that are attached with adhesive. If necessary, you can also use a screw into the sill, but that has not been required. 

First attach the window mount.

Next, attach the sill mount.

Wait 24 hours for the adhesives to set and you can now use the window opener.


## Sending commands

Commands are sent via HTTP requests

Follow the instructions outlined in the ![firmware](/firmware) folder.


## Node-RED workflow

Use Node-RED in Home Assistant to automate everything. Click the image below to watch a YouTube video on how it works.

[![Youtube Link](/media/node-red-flow.jpg)](https://youtu.be/ou7uRED_ff0)
