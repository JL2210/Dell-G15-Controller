#!/bin/python
import os
import sys
import pexpect
import tempfile
import awelc
import time
import argparse
from patch import g15_5520_patch
from patch import g15_5515_patch
from patch import g15_5511_patch

class Command():

    def __init__(self):
        self.power_modes_dict = {
            "USTT_Balanced" : "0xa0",
            "USTT_Performance" : "0xa1",
            # "USTT_Cool" : "0xa2",   #Does not work
            "USTT_Quiet" : "0xa3",
            "USTT_FullSpeed" : "0xa4",
            "USTT_BatterySaver" : "0xa5",
            "G Mode" : "0xab",
            "Manual" : "0x0",
        }
        self.acpi_call_dict = {
            "get_laptop_model" : ["0x1a", "0x02", "0x02"],
            "get_power_mode" : ["0x14", "0x0b", "0x00"],
            "set_power_mode" : ["0x15", "0x01"],    #To be used with a parameter
            "toggle_G_mode" : ["0x25", "0x01"],
            "get_G_mode" : ["0x25", "0x02"],
            "set_fan1_boost" : ["0x15", "0x02", "0x32"],            #To be used with a parameter
            "get_fan1_boost" : ["0x14", "0x0c", "0x32"],
            "get_fan1_rpm" : ["0x14", "0x05", "0x32"],
            "get_cpu_temp" : ["0x14", "0x04", "0x01"],
            "set_fan2_boost" : ["0x15", "0x02", "0x33"],            #To be used with a parameter
            "get_fan2_boost" : ["0x14", "0x0c", "0x33"],
            "get_fan2_rpm" : ["0x14", "0x05", "0x33"],
            "get_gpu_temp" : ["0x14", "0x04", "0x06"]
        }

        
        self.checkLaptopModel()

    def checkLaptopModel(self):
        # Check laptop model and inform user if model is not supported.
        commands = {
            5525: ("\\_SB.AMW3.WMAX 0 {} {{{}, {}, {}, 0x00}}", "0xc80", None),
            5520: ("\\_SB.AMWW.WMAX 0 {} {{{}, {}, {}, 0x00}}", "0xc80", g15_5520_patch),
            5515: ("\\_SB.AMW3.WMAX 0 {} {{{}, {}, {}, 0x00}}", "0x12c0", g15_5515_patch),
            7620: ("\\_SB.AMWW.WMAX 0 {} {{{}, {}, {}, 0x00}}", "0x12c0", None),
        }
        
        for key, value in commands.items():
            self.acpi_cmd = value[0]
            laptop_model = self.acpi_call("get_laptop_model")
            #print(f"acpi call result: {laptop_model}")
            if (laptop_model == value[1]):
                print("Detected Dell G15 {}. Laptop model id: {}".format(key, value[1]))
                self.is_dell_g15 = True
                if(value[2]):
                    value[2](self)
                return
        
    def combobox_power(self, choice):
        self.fan1_boost = 0
        self.fan2_boost = 0
        message = ""
        
        # Set power mode
        mode = self.power_modes_dict[choice]
        self.acpi_call("set_power_mode",mode)
        # Get current power mode to confirm
        result = self.acpi_call("get_power_mode")
        if (result == mode):   #Expected result
            message = "Power mode set to {}.\n".format(choice)
        else:
            message = "Error! Command returned: {}, but expecting {}.\n".format(str(result),str(mode))
        # Get G Mode
        result = self.acpi_call("get_G_mode")
        if (choice == "G Mode") != (result == "0x1"):  #Toggle G Mode if needed.
            #Toggle G mode
            result_toggle = self.acpi_call("toggle_G_mode")
            if (("0x1" if choice == "G Mode" else "0x0") != result_toggle): 
                message = message + "Expected to read G Mode = {} but read {}!\n".format(choice == "G Mode",result_toggle)

        print(message)
    
    def slider_fan1(self, new_val):
        #Fan1 has id 0x32
        #Get current fan boost
        fan1_last_boost = self.acpi_call("get_fan1_boost")
        #Set new fan boost
        self.acpi_call("set_fan1_boost","0x{:2X}".format(new_val))
        #Get current fan boost
        fan1_new_boost = self.acpi_call("get_fan1_boost")
        print("Fan1 Boost: {:.0f}% to {:.0f}%.".format(int(fan1_last_boost,0)/0xff*100,int(fan1_new_boost,0)/0xff*100))
    
    def slider_fan2(self, new_val):
        #Fan2 has id 0x33
        #Get current fan boost
        fan2_last_boost = self.acpi_call("get_fan2_boost")
        #Set new fan boost
        self.acpi_call("set_fan2_boost","0x{:2X}".format(new_val))
        #Get current fan boost
        fan2_new_boost = self.acpi_call("get_fan2_boost")
        print("Fan2 Boost: {:.0f}% to {:.0f}%.".format(int(fan2_last_boost,0)/0xff*100,int(fan2_new_boost,0)/0xff*100))
    
    def get_rpm_and_temp(self):
        #Get current rpm and temp
        fan1_rpm = self.acpi_call("get_fan1_rpm")
        cpu_temp = self.acpi_call("get_cpu_temp")
        fan2_rpm = self.acpi_call("get_fan2_rpm")
        gpu_temp = self.acpi_call("get_gpu_temp")
        print("fan1 {} RPM, {} °C".format(int(fan1_rpm,0),int(cpu_temp,0)))
        print("fan2 {} RPM, {} °C".format(int(fan2_rpm,0),int(gpu_temp,0)))
    
    #Execute given command in elevated shell
    def acpi_call(self, cmd, arg1="0x00", arg2="0x00"):
        args = self.acpi_call_dict[cmd]
        if len(args)==4:
            cmd_current = self.acpi_cmd.format(args[0], args[1], args[2], args[3])
        elif len(args)==3:
            cmd_current = self.acpi_cmd.format(args[0], args[1], args[2], arg1)
        elif len(args)==2:
            cmd_current = self.acpi_cmd.format(args[0], args[1], arg1, arg2)
        else:
            cmd_current=""
        #print(cmd_current)
        # acpi_call goes nuts if you read and write the file without closing
        with open("/proc/acpi/call", "wb") as vfile:
            vfile.write(cmd_current.encode(encoding="ascii"))
            vfile.flush()
        with open("/proc/acpi/call", "rb") as vfile:
            result = vfile.read().rstrip(b'\x00').decode(encoding="ascii")
        return result

    def split_rgb(self, rgb):
        r = rgb & 0xff0000 >> 16
        g = rgb & 0x00ff00 >>  8
        b = rgb & 0x0000ff >>  0
        return (r, g, b)

    # Apply given colors to keyboard.
    def apply_static(self, rgb):
        awelc.set_static(*self.split_rgb(rgb))

    def apply_morph(self, rgb_morph, duration):
        awelc.set_morph(*self.split_rgb(rgb_morph), duration)
    
    def apply_color_and_morph(self, rgb, rgb_morph, duration):
        awelc.set_color_and_morph(*self.split_rgb(rgb), *self.split_rgb(rgb_morph), duration)
    
    def remove_animation(self):
        awelc.remove_animation()

    def dim(self, dim):
        awelc.set_dim(dim)


def led_subparser(arguments, cli):
    match arguments.ledsubparser_name:
        case 'static':
            rgb = int(arguments.rgb, 16)
            cli.apply_static(rgb)
        case 'morph':
            rgbm = int(arguments.rgbm, 16)
            duration = int(arguments.duration)
            cli.apply_morph(rgbm, duration)
        case 'color_and_morph':
            rgb = int(arguments.rgb, 16)
            rgbm = int(arguments.rgbm, 16)
            duration = int(arguments.duration)
            cli.apply_color_and_morph(rgb, rgbm, duration)
        case 'none':
            cli.remove_animation()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog="DellGController",
                                    description="An app to control keyboard backlight, power mode and fan speed on some Dell and Alienware laptops")
    subparser = parser.add_subparsers(dest='subparser_name', required=True)
    leds = subparser.add_parser('leds', help="Control LED color and animation")
    ledsubparser = leds.add_subparsers(dest='ledsubparser_name', required=True)

    static = ledsubparser.add_parser('static', help="Static color")
    morph = ledsubparser.add_parser('morph', help="Morphing color")
    color_and_morph = ledsubparser.add_parser('color_and_morph', help="Static+Morphing color")
    led_none = ledsubparser.add_parser('none', help="Disable LEDs")
    dim = ledsubparser.add_parser('dim', help="set LED brightness")
    get = ledsubparser.add_parser('get', help="get LED info")

    static.add_argument('rgb', help="Static RGB value in hex form")
    color_and_morph.add_argument('rgb', help="Static RGB value in hex form")
    morph.add_argument('rgbm', help="Morphing RGB value in hex form")
    morph.add_argument('duration', help="Morph duration in milliseconds")
    color_and_morph.add_argument('rgbm', help="Morphing RGB value in hex form")
    color_and_morph.add_argument('duration', help="Morph duration in milliseconds")
    dim.add_argument('dim', help="dim 0-100, 100 is off")

    arguments = parser.parse_args()

    cli = Command()

    match arguments.subparser_name:
        case 'leds':
            led_subparser(arguments, cli)

#    while True:
#        pass
