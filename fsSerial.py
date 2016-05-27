## Copyright (c) 2016, FlySorter LLC
##

import sys
import glob
import serial
import time

# Serial communications class that is used for multiple devices.
#
class fsSerial:
    """Serial class for generic serial device."""
    
    WaitTimeout = 3
    portName = ""

    def __init__(self, port, baud = 9600, timeout = float(0.1)):
        self.isOpened = False
        try:
            self.ser = serial.Serial(port, baudrate = baud, timeout = timeout)
        except:
            print "Failed to open port", port
            return
        self.isOpened = True

    def close(self):
        self.ser.close()
        
    # Retrieve any waiting data on the port
    def getSerOutput(self):
        #print "GSO:"
        output = ''
        while True:
            # read() blocks for the timeout set above *if* there is nothing to read
            #   otherwise it returns immediately
            byte = self.ser.read(1)
            if byte is None or byte == '':
                break
            output += byte
            if byte == '\n':
                break
        #print "GSO Output:", output
        return output

    # Block and wait for the device to reply with "ok" or "OK"
    # Times out after self.WaitTimeout (set above)
    def waitForOK(self):
        #print "WFO:"
        output = ''
        timeoutMax = self.WaitTimeout / self.ser.timeout
        timeoutCount = 0
        while True:
            byte = self.ser.read(1)
            if byte is None or byte == '':
                timeoutCount += 1
                time.sleep(1)
            else:
                output += byte
            if timeoutCount > timeoutMax:
                print 'Serial timeout.'
                break
            if byte == '\n':
                break
        #print "WFO Output:", output
        if (output.rstrip('\r\n') != '') and ( not output.startswith("ok") ) and ( not output.startswith("OK") ):
            print "Unexpected serial output:", output.rstrip('\r\n'), "(", ':'.join(x.encode('hex') for x in output), ")"

    # Send a command to the device via serial port
    # Asynchronous by default - doesn't wait for reply
    def sendCmd(self, cmd):
        #print "SC:", cmd
        self.ser.write(cmd)
        self.ser.flush()

    # Send a command to the device via serial port
    # Waits to receive reply of "ok" or "OK" via waitForOK()
    def sendSyncCmd(self, cmd):
        #print "SSC:", cmd
        self.ser.flushInput()
        self.ser.write(cmd)
        self.ser.flush()
        self.waitForOK()

    # Send a command and retrieve the reply
    def sendCmdGetReply(self, cmd):
        self.ser.flushInput()
        self.ser.write(cmd)
        self.ser.flush()
        return self.getSerOutput()

