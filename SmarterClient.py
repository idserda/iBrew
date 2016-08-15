# -*- coding: utf8 -*-

import socket
import os
import sys
import string

from SmarterProtocol import *

#------------------------------------------------------
# SMARTER CLIENT INTERFACE
#
# Python interface to iKettle 2.0 & Smarter Coffee Devices
#
# https://github.com/Tristan79/iBrew
#
# 2016 Copyright © 2016 Tristan (@monkeycat.nl)
#
# White Tea Leaf Edition (rev 4)
#------------------------------------------------------



#------------------------------------------------------
# CLIENT INTERFACE CLASS
#------------------------------------------------------


class SmarterClient:


    def init(self):
        # network
        self.host                       = "192.168.4.1"
        self.port                       = 2081
        self.connected                  = False
        self.dump                       = False
        
        # device
        self.commandStatus              = Smarter.StatusSucces
        self.sendMessage                = None
        self.responseMessage            = None
        self.readMessage                = None
        self.statusMessage              = None
        
        # device info
        self.device                     = "None"
        self.version                    = 0
    
        # kettle
        self.isKettle                   = False
        self.kettleStatus               = Smarter.KettleReady
        self.temperature                = 0
        self.onBase                     = False
        self.defaultTemperature         = 100
        self.defaultKeepWarmTime        = 0
        self.defaultFormula             = False
        self.defaultFormulaTemperature  = 50
        
        # coffee
        self.isCoffee                   = False
        self.coffeeStatus               = 0 # unknown
        self.cups                       = 1
        self.strength                   = Smarter.CoffeeMedium
        
        # watersensor
        self.waterSensorBase            = 0
        self.waterSensor                = 0
 
        # Wifi
        self.Wifi                       = []
        self.WifiFirmware               = "None"


    def __init__(self,host = "192.168.4.1", dump = False):
        self.init()
        self.dump = dump
        self.host = host
        self.connect()


    def __del__(self):
        self.disconnect()



    #------------------------------------------------------
    # CONNECTION
    #------------------------------------------------------


    def connect(self):
        try:
            networksocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            networksocket.connect((self.host, self.port))
        except socket.error, msg:
            raise SmarterError("Could not connect to + " + self.host + " (" + msg[1] + ")")
    
        self.socket = networksocket
        self.connected = True
        self.read()
        self.device_info()
        #self.device_history()
        if self.isKettle:
            self.kettle_settings()
            self.calibrate_base()


    def disconnect(self):
        if self.connected:
            self.init()
            try:
                self.socket.close()
            except socket.error, msg:
                raise SmarterError("Could not disconnect from + " + self.host + " (" + msg[1] + ")")



    #------------------------------------------------------
    # MESSAGE RESPONSE DECODERS
    #------------------------------------------------------


    def decode_ResponseSettings(self,message):
        self.defaultKeepWarmTime     = Smarter.raw_to_number(message[2])
        self.defaultTemperature      = Smarter.raw_to_temperature(message[1])
        self.defaultFormula          = Smarter.raw_to_temperature(message[3])


    def decode_ResponseStatus(self,message):
        self.statusMessage = message
        if self.isKettle:
            self.kettleStatus        = Smarter.raw_to_number(message[1])
            self.temperature         = Smarter.raw_to_temperature(message[2])
            self.waterSensor         = Smarter.raw_to_watersensor(message[4],message[3])
            self.onBase              = Smarter.is_on_base(message[2])
        elif self.isCoffee:
            # guess work here
            self.coffeeStatus        = Smarter.raw_to_number(message[1])
            self.waterSensor         = Smarter.raw_to_watersensor(message[3],message[2])
            self.strength            = Smarter.raw_to_strength(message[4])
            self.cups                = Smarter.raw_to_cups(message[5])


    def decode_ResponseDeviceInfo(self,message):
        self.isCoffee = False
        self.isKettle = False
        
        if Smarter.raw_to_number(message[1]) == 1:
            self.isKettle = True
            self.device = "iKettle 2.0"
        if Smarter.raw_to_number(message[1]) == 2:
            self.isCoffee = True
            self.device = "SmarterCoffee"
        self.version = Smarter.raw_to_number(message[2])


    def decode_ResponseBase(self,message):
        self.waterSensorBase = Smarter.raw_to_watersensor(message[2],message[1])


    def decode_ResponseCommandStatus(self,message):
        self.commandStatus = Smarter.raw_to_number(message[1])


    def decode_ResponseWifiFirmware(self,message):
        s = ""
        for i in range(1,len(message)-1):
            x = str(message[i])
            if x in string.printable:
                s += x
        self.WifiFirmware = s


    def decode_ResponseWifiList(self,message):
        a = ""
        w = []
        db = False
        for i in range(1,len(message)-1):
            x = str(message[i])
            if x == ',':
               db = True
               d = ""
               continue
            elif x == '}':
               db = False
               w += [(a,d)]
               a = ""
               continue
            elif not db and x in string.printable:
                a += x
            elif db and x in string.printable:
                d += x
        from operator import itemgetter
    
        # most powerfull wifi on top
        self.Wifi = sorted(w,key=itemgetter(1))


    def decode_ResponseHistory(self,message):
        pass
    


    #------------------------------------------------------
    # TRANSMISSION
    #------------------------------------------------------


    # MESSAGE READ
  
    def read_message(self):
        if not self.connected:
            self.connect()
        try:
            message = ""
            raw = self.socket.recv(1)
            id = Smarter.raw_to_number(raw)
            
            # debug
            #print "[" + Smarter.number_to_code(id) + "]"
            minlength = Smarter.message_response_length(id)
            
            # we got an empty message read the next one...
            #if id == Smarter.MessageTail or id == Smarter.MessageEmpty:
            #    raw = self.socket.recv(1)

            i = 1
            while raw != Smarter.number_to_raw(Smarter.MessageTail) or (minlength > 0 and raw == Smarter.number_to_raw(Smarter.MessageTail) and i < minlength):
            
                message += raw
                raw = self.socket.recv(1)
                
                # debug
                #print "[" + Smarter.raw_to_code(raw) + "]"
                
                i += 1
            message += raw
            self.readMessage = message
            return message

        except socket.error, msg:
            raise SmarterError("Could not read message (" + msg[1] + ")")


    # MESSAGE READ PROTOCOL

    def read(self):
        message = self.read_message()
        id = Smarter.raw_to_number(message[0])
        if   id == Smarter.ResponseCommandStatus:   self.decode_ResponseCommandStatus(message)
        elif id == Smarter.ResponseBase:            self.decode_ResponseBase(message)
        elif id == Smarter.ResponseHistory:         self.decode_ResponseHistory(message)
        elif id == Smarter.ResponseSettings:        self.decode_ResponseSettings(message)
        elif id == Smarter.ResponseDeviceInfo:      self.decode_ResponseDeviceInfo(message)
        elif id == Smarter.ResponseWifiFirmware:    self.decode_ResponseWifiFirmware(message)
        elif id == Smarter.ResponseWifiList:        self.decode_ResponseWifiList(message)
        elif id == Smarter.ResponseStatus:          self.decode_ResponseStatus(message)
        
        if self.dump:
            self.print_message_read(message)
 
        return message


    # MESSAGE SEND

    def send_message(self,message):
        try:
            if len(message) > 0 and message[len(message)-1] == Smarter.MessageTail:
                messageTail = message
            elif len(message) > 0:
                messageTail = message + Smarter.number_to_raw(Smarter.MessageTail)
            else:
                raise SmarterError("Cannot send an empty message")
            self.socket.send(messageTail)
        except socket.error, msg:
            raise SmarterError("Could not read message (" + msg[1] + ")")
        
        self.sendMessage = messageTail
        if self.dump:
            self.print_message_send(messageTail)


    # MESSAGE SEND PROTOCOL

    def send_command(self,id,arguments=""):
        self.send(Smarter.number_to_raw(id) + arguments)


    def send(self,message):
        self.send_message(message)
        self.read()
 
        while Smarter.raw_to_number(self.readMessage[0]) == Smarter.ResponseStatus:
             self.read()
        
        self.responseMessage = self.readMessage
        
        # read until right message.... no threaded read
        
       # Smarter.message_connection(raw_to_number(self.readMessage[0])[0]
        self.read()
        while Smarter.raw_to_number(self.readMessage[0]) != Smarter.ResponseStatus:
            self.read()
       


    #------------------------------------------------------
    # COMMANDS: Calibrate
    #------------------------------------------------------


    def calibrate(self):
        self.send_command(Smarter.CommandCalibrate)


    def calibrate_base(self):
        self.send_command(Smarter.CommandBase)


    def calibrate_store_base(self,base = 1000):
        if base < 256: # base > 65535
            self.send_command(Smarter.CommandStoreBase,Smarter.watersensor_to_raw(256))
        else:
            self.send_command(Smarter.CommandStoreBase,Smarter.watersensor_to_raw(base))



    #------------------------------------------------------
    # COMMANDS: iKettle 2.0 & Smarter Coffee
    #------------------------------------------------------


    def device_raw(self,code):
        self.send(Smarter.string_to_message(code))


    def device_info(self):
        self.send_command(Smarter.CommandDeviceInfo)


    def device_stop(self):
        self.send_command(Smarter.CommandStop)


    def device_reset(self):
        self.send_command(Smarter.CommandReset)


    def device_update(self):
        self.send_command(Smarter.CommandUpdate)


    def device_device_time(self,time):
        # FIX decoding here
        self.send_command(Smarter.CommandDeviceTime)


    def device_history(self):
        self.send_command(Smarter.CommandHistory)



    #------------------------------------------------------
    # COMMANDS: Wifi
    #------------------------------------------------------


    def wifi_firmware(self):
        self.send_command(Smarter.CommandWifiFirmware)


    def wifi_scan(self):
        self.send_command(Smarter.CommandWifiScan)


    def wifi_reset(self):
        self.send_command(Smarter.CommandWifiReset)


    def wifi_connect(self):
        self.send_command(Smarter.CommandWifiConnect)


    def wifi_password(self,password=""):
        self.send_command(Smarter.CommandWifiPassword,Smarter.text_to_raw(password))


    def wifi_name(self,name=""):
        self.send_command(Smarter.CommandWifiName,Smarter.text_to_raw(name))



    #------------------------------------------------------
    # COMMANDS: iKettle 2.0
    #------------------------------------------------------

 
    def kettle_store_settings(self,temperature = 100, timer = 0, formulaOn = False, formulaTemperature = 75):
        if self.isKettle:
            self.send_command(Smarter.CommandStoreSettings,Smarter.temperature_to_raw(temperature) + Smarter.timer_to_raw(timer) + self.bool_to_raw(formulaOn) + Smarter.temperature_to_raw(formulaTemperature))
        else:
            raise SmarterError("You need a kettle to store settings")


    def kettle_settings(self):
        if self.isKettle:
            self.send_command(Smarter.CommandSettings)
        else:
            raise SmarterError("You need a kettle to get its settings")


    def kettle_heat(self):
        if self.isKettle:
            self.send_command(Smarter.CommandHeatDefault)
        else:
            raise SmarterError("You need a kettle to heat water")


    def kettle_formula_heat(self):
        if self.isKettle:
            self.send_command(Smarter.CommandFormula)
        else:
            raise SmarterError("You need a kettle to heat water in formula mode")



    #------------------------------------------------------
    # COMMANDS: Smarter Coffee
    #------------------------------------------------------


    def coffee_brew(self):
        if self.isCoffee:
            self.send_command(Smarter.CommandBrew)
        else:
            raise SmarterError("You need a coffee machine to brew coffee")


    def coffee_hotplate_off(self):
        if self.isCoffee == True:
            self.send_command(Smarter.CommandHotplateOff)
        else:
            raise SmarterError("You need a coffee machine to turn off the hotplate")
 

    def coffee_hotplate_on(self, timer=5):
        if self.isCoffee == True:
            self.send_command(Smarter.CommandHotplate,Smarter.timer_to_raw(timer))
        else:
            raise SmarterError("You need a coffee machine to turn on the hotplate")


    def coffee_grinder(self):
        if self.isCoffee == True:
            self.send_command(Smarter.CommandGrinder)
        else:
            raise SmarterError("You need a coffee machine to grind beans")


    def coffee_cups(self,cups=1):
        if self.isCoffee == True:
            self.send_command(Smarter.CommandCups,Smarter.cups_to_raw(cups))
        else:
            raise SmarterError("You need a coffee machine to select the number of cups to brew")


    def coffee_strength(self,strength="medium"):
        if self.isCoffee == True:
            self.send_command(Smarter.CommandStrenght,Smarter.strength_to_raw(strength))
        else:
            raise SmarterError("You need a coffee machine to select the coffee strength")



    #------------------------------------------------------
    # STRING/PRINT SMARTER INFO
    #------------------------------------------------------


    def print_info(self):
        print self.device + " v" + str(self.version)


    def print_watersensor_base(self):
        print "Watersensor calibration base value: " + str(self.waterSensorBase)


    def print_wireless_networks(self):
        print
        print "         Signal   Wireless Network"
        for i in range(0,len(self.Wifi)):
            
            quality = Smarter.dbm_to_quality(int(self.Wifi[i][1]))
            
            s = ""
            for x in range(quality / 10,10):
                s += " "
            for x in range(0,quality / 10):
                s += "█"

            print "     " + s + "   " + self.Wifi[i][0]
        print

    def print_wifi_firmware(self):
        print
        print self.WifiFirmware
        print

    def string_kettle_settings(self):
        default = "Boil water to " + str(self.defaultTemperature) +  "ºC"
        if self.defaultFormula:
            sep = ""
            if self.defaultKeepWarmTime > 0:
                sep = ","
            else:
                sep = " and"
            default = default + sep + " let it cool down to " + str(self.defaultFormulaTemperature) +  "ºC"
        if self.defaultKeepWarmTime > 0:
            default = default + " and keep it warm for " + str(self.defaultKeepWarmTime) + " minutes"
        return default

    def print_kettle_settings(self):
        if self.isKettle:
            print self.string_kettle_settings()
   

    def print_history(self):
        print "Unknown settings please add!"


    def string_cups(self,cups):
        if cups == 1:
            return "1 cup"
        else:
            return str(self.cups) + " cups"
            
    def print_short_status(self):
        if self.isKettle:
            if self.onBase:
                print Smarter.status_kettle_description(self.kettleStatus) + " on base: Temperature " + str(self.temperature) + "ºC, watersensor " + str(self.waterSensor)
            else:
                print Smarter.status_kettle_description(self.kettleStatus) + " off base"
        if self.isCoffee == True:
            print Smarter.status_coffee_description(self.coffeeStatus) + ": Watersensor: " + str(self.waterSensor) + ", setting: " + Smarter.number_to_strength(self.strength) + " " + self.string_cups(self.cups)


    def print_status(self):
        m = self.read()
        print
        if self.isKettle:
            if self.onBase:
                print "Status         " + Smarter.status_kettle_description(self.kettleStatus)
                print "Temperature    " + str(self.temperature) +  "ºC"
                print "Water sensor   " + str(self.waterSensor) + " (calibration base " + str(self.waterSensorBase) + ")"
            else:
                print "Status         Off base"
            print "Default boil   " + self.string_kettle_settings()
        if self.isCoffee == True:
            print "Status         " + Smarter.status_coffee_description(self.coffeeStatus)
            print "Water sensor   " + str(self.waterSensor)
            print "Setting        " + Smarter.number_to_strength(self.strength) + " " + self.string_cups(self.cups)
        print


    def print_connect_status(self):
        print "Connected to " + self.device + " Firmware v" + str(self.version) + " (" + self.host + ")"


    def print_message_send(self,message):
        print "Message Send:     [" + Smarter.message_description(Smarter.raw_to_number(message[0])) + "] [" + Smarter.message_to_codes(message) + "]"


    def print_message_read(self,message):
        id = Smarter.raw_to_number(message[0])
        print "Message Received: [" + Smarter.message_description(id) + "] [" + Smarter.message_to_codes(message) + "]"
        if   id == Smarter.ResponseCommandStatus:   print "Command replied: " + Smarter.status_command(self.commandStatus)
        elif id == Smarter.ResponseWifiList:        self.print_wireless_networks()
        elif id == Smarter.ResponseWifiFirmware:    self.print_wifi_firmware()
        elif id == Smarter.ResponseHistory:         self.print_history()
        elif id == Smarter.ResponseSettings:        self.print_kettle_settings()
        elif id == Smarter.ResponseDeviceInfo:      self.print_info()
        elif id == Smarter.ResponseBase:            self.print_watersensor_base()
        elif id == Smarter.ResponseStatus:          self.print_short_status()
        else:                                       print "Unknown Reply Message"
