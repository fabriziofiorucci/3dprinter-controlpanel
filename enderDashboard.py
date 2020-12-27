#!/usr/bin/python3

# I2C bus
# 0x26 - LCD Display
# 0x27 - PCF8574

# RJ 11 pinout
# 1 - PCF8574 Interrupt
# 2 - GND
# 3 - +5vcc
# 4 - SDA
# 5 - SCL
# 6 - NC

import sys
import RPi.GPIO as GPIO
import smbus
import time
import yaml
import subprocess

# define I2C bus number
BUS_NUMBER = 1

# LCD configuration
LCD_ADDR=0x26
LCD_WIDTH=16   # Maximum characters per line
LCD_CHR=1 # Mode - Sending data
LCD_CMD=0 # Mode - Sending command

LCD_LINE_1 = 0x80 # LCD RAM address for the 1st line
LCD_LINE_2 = 0xC0 # LCD RAM address for the 2nd line
LCD_LINE_3 = 0x94 # LCD RAM address for the 3rd line
LCD_LINE_4 = 0xD4 # LCD RAM address for the 4th line

LCD_BACKLIGHT  = 0x08  # On
#LCD_BACKLIGHT = 0x00  # Off

ENABLE = 0b00000100 # Enable bit

# Timing constants
E_PULSE = 0.0005
E_DELAY = 0.0005

# PCF8574 configuration (INT pin connected to VCC through 4.7kOhm pullup resistor)
PCF8574_ADDR=0x27
PCF8574_INT_PIN=17

# define bitmask to detect keypress
KEY_LEFT=1
KEY_UP=4
KEY_DOWN=2
KEY_RIGHT=8
KEY_NONE=255

bus = smbus.SMBus(BUS_NUMBER)

def lcd_init():
  # Initialise display
  lcd_byte(0x33,LCD_CMD) # 110011 Initialise
  lcd_byte(0x32,LCD_CMD) # 110010 Initialise
  lcd_byte(0x06,LCD_CMD) # 000110 Cursor move direction
  lcd_byte(0x0C,LCD_CMD) # 001100 Display On,Cursor Off, Blink Off 
  lcd_byte(0x28,LCD_CMD) # 101000 Data length, number of lines, font size
  lcd_byte(0x01,LCD_CMD) # 000001 Clear display
  time.sleep(E_DELAY)

def lcd_byte(bits, mode):
  # Send byte to data pins
  # bits = the data
  # mode = 1 for data
  #        0 for command

  bits_high = mode | (bits & 0xF0) | LCD_BACKLIGHT
  bits_low = mode | ((bits<<4) & 0xF0) | LCD_BACKLIGHT

  # High bits
  bus.write_byte(LCD_ADDR, bits_high)
  lcd_toggle_enable(bits_high)

  # Low bits
  bus.write_byte(LCD_ADDR, bits_low)
  lcd_toggle_enable(bits_low)

def lcd_toggle_enable(bits):
  # Toggle enable
  time.sleep(E_DELAY)
  bus.write_byte(LCD_ADDR, (bits | ENABLE))
  time.sleep(E_PULSE)
  bus.write_byte(LCD_ADDR,(bits & ~ENABLE))
  time.sleep(E_DELAY)

def lcd_string(message,line):
  # Send string to display

  message = message.ljust(LCD_WIDTH," ")

  lcd_byte(line, LCD_CMD)

  for i in range(LCD_WIDTH):
    lcd_byte(ord(message[i]),LCD_CHR)

def lcd_clear():
  lcd_string("",LCD_LINE_1)
  lcd_string("",LCD_LINE_2)

def readKeys():
  "Reads the control panel keys"

  # read PCF8574
  currentVal = bus.read_byte(PCF8574_ADDR)

  return currentVal

def isKeyPressed(keysVal,keyMask):
  "Returns true if the given button is pressed"

  if (keysVal & keyMask == 0):
    return 1

  return 0

def readMenu(cfgFile):
  "Reads the menu from the configuration file"

  print("Reading menu")
  with open(cfgFile) as file:
    menu=yaml.load(file,Loader=yaml.FullLoader)

  numberOfItems=0
  for item,doc in menu.items():
    numberOfItems=numberOfItems+1
    print("Menu item:",item)
    for i in doc:
      print("-- Option:",i)
      print("   Name:",i['name'])
      print("   Cmd :",i['cmd'])

  return menu,numberOfItems-1

def main(cfgFile):
  print("Reading configuration from "+cfgFile)

  enderMenu,enderMenuNumOfItems=readMenu(cfgFile)

  # PULLUP all ports to enable button state readout
  bus.write_byte(PCF8574_ADDR,255)

  # Sets up PCF8574 interrupt line
  GPIO.setmode(GPIO.BCM)
  # Pin BCM interrupt pin
  GPIO.setup(PCF8574_INT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

  lcd_init()

  lcd_string("Ender 3 Panel",LCD_LINE_1)
  lcd_string("v1.0 - 2020 FF75",LCD_LINE_2)
  time.sleep(2)
  lcd_clear()

  isMenuTopLevel=True
  menuItemCounter=0
  menuItemOptionCounter=0
  menuItemOptionCmd=""

  while 1 == 1:
    try:
      lcd_clear()
      if(isMenuTopLevel==True):
        # Displaying top level menu
        i=0
        menuItemOptions=""
        for k,v in enderMenu.items():
          print("menuItemCounter:",menuItemCounter," i:",i," Item:",k)
          if(i==menuItemCounter):
            lcd_string(">"+k,LCD_LINE_1)
            menuItemOptions=v
          if(i==menuItemCounter+1):
            lcd_string(" "+k,LCD_LINE_2)
          i=i+1
      else:
        # Displaying second level menu options
        i=0
        enderMenuNumOfOptionItems=-1
        for option in menuItemOptions:
          enderMenuNumOfOptionItems=enderMenuNumOfOptionItems+1
          print("-- Option:",option)
          print("   Name:",option['name'])
          print("   Cmd :",option['cmd'])
          if(i==menuItemOptionCounter):
            lcd_string(">"+option['name'],LCD_LINE_1)
            menuItemOptionCmd=option['cmd']
          if(i==menuItemOptionCounter+1):
            lcd_string(" "+option['name'],LCD_LINE_2)
          i=i+1

      # Waiting for keypad interrupt
      GPIO.wait_for_edge(PCF8574_INT_PIN, GPIO.FALLING)

      currentVal=readKeys()

      if(currentVal!=KEY_NONE):
        print("PCF8574:", currentVal)
        print("Up     : ",isKeyPressed(currentVal,KEY_UP))
        print("Left   : ",isKeyPressed(currentVal,KEY_LEFT))
        print("Down   :  ",isKeyPressed(currentVal,KEY_DOWN))
        print("Right  : ",isKeyPressed(currentVal,KEY_RIGHT))
        print("------------------")

        if(isMenuTopLevel==True):
          if(isKeyPressed(currentVal,KEY_UP)):
            if(menuItemCounter>0):
              print("Menu scroll down")
              menuItemCounter=menuItemCounter-1
          if(isKeyPressed(currentVal,KEY_DOWN)):
            if(menuItemCounter<enderMenuNumOfItems):
              print("Menu scroll up")
              menuItemCounter=menuItemCounter+1
          if(isKeyPressed(currentVal,KEY_RIGHT)):
            print("Menu enter item")
            isMenuTopLevel=False
        else:
          if(isKeyPressed(currentVal,KEY_UP)):
            if(menuItemOptionCounter>0):
              print("Menu option scroll down")
              menuItemOptionCounter=menuItemOptionCounter-1
          if(isKeyPressed(currentVal,KEY_DOWN)):
            if(menuItemOptionCounter<enderMenuNumOfOptionItems):
              print("Menu option scroll up")
              menuItemOptionCounter=menuItemOptionCounter+1
          if(isKeyPressed(currentVal,KEY_RIGHT)):
            print("Menu run command: ",menuItemOptionCmd)
            # Run system command here
            retVal=subprocess.call(menuItemOptionCmd,shell=True)
            print("Command return value: ",retVal)
          if(isKeyPressed(currentVal,KEY_LEFT)):
            print("Menu leave item")
            isMenuTopLevel=True

        #lcd_string(
        #  "U:"+str(isKeyPressed(currentVal,KEY_UP))+
        #  " L:"+str(isKeyPressed(currentVal,KEY_LEFT))+
        #  " D:"+str(isKeyPressed(currentVal,KEY_DOWN))+
        #  " R:"+str(isKeyPressed(currentVal,KEY_RIGHT)),LCD_LINE_2)
        #lcd_string("Raw: "+str(currentVal),LCD_LINE_1)
      else:
        lcd_clear()
    except KeyboardInterrupt:
      GPIO.cleanup()       # clean up GPIO on CTRL+C exit
      exit()

if __name__ == '__main__':

  if len(sys.argv) != 2:
    print(sys.argv[0]+" [configfile]")
  else:
    try:
      main(sys.argv[1])
    except KeyboardInterrupt:
      pass
    finally:
      lcd_byte(0x01, LCD_CMD)
