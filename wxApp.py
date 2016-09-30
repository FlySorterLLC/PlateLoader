#!/usr/bin/python
# 
# Copyright (c) 2016, FlySorter LLC
# See the included LICENSE file for more information
#

# This program provides a graphical interface
# to a robot that uses a FlySorter Fly Dispenser
# to load 96 well plates (FlySorter FlyPlates).

# The program uses wxWidgets to handle the GUI elements,
# and a separate serial class to interface with the USB devices.


import wx
from threading import *
import numpy as np
import sys
import glob
import time

import fsSerial

# Configuration parameters

# The robotic X/Y coordinates of the first (A1) and last (H12)
# wells in the plate.
startWellPoint = np.array([-49.25, 31.0])
endWellPoint = np.array([50.75, -33.0])

# Z heights for clearing and engaging the wells.
# Clearance height must be high enough that the nozzle is above
# the plate enough that the plate can be removed.
clearanceHeight = 35.
wellHeight = 19

# End configuration parameters

# Set up a new wx event that we can pass between the 
# worker thread and the main wx app
EVT_RESULT_ID = wx.NewId()

def EVT_RESULT(win, func):
  """Define Result Event."""
  win.Connect(-1, -1, EVT_RESULT_ID, func)

# data in event should be:
#
# None     - if worker thread completed plate loading task without error
# 1 - 96   - if worker thread successfully loaded that well number (1-based)
# -1 - -96 - if worker thread didn't load a particular well (1-based)
#
class ResultEvent(wx.PyEvent):
  """Simple event to carry arbitrary result data."""
  def __init__(self, data):
    """Init Result Event."""
    wx.PyEvent.__init__(self)
    self.SetEventType(EVT_RESULT_ID)
    self.data = data

# Thread class that dispenses flies and moves the robot
# (a separate thread so the app remains responsive)
class WorkerThread(Thread):
  """Worker Thread Class."""
  def __init__(self, notify_window, start_val=0):
    """Init Worker Thread Class."""
    Thread.__init__(self)
    self._notify_window = notify_window
    self._want_abort = 0
    self._run_status = 1
    self._currentWell = start_val
    self.start()

  def run(self):
    """Run Worker Thread."""
    # First, move Z to clearance height
    robot.sendSyncCmd("G01 Z{0}\n".format(clearanceHeight))
    while ( self._want_abort == 0 ):
       # Move to the next well 
       wellCoords = getWell(self._currentWell)
       robot.sendSyncCmd("G01 X{0} Y{1}\n".format(wellCoords[0],
                                                  wellCoords[1]))
       robot.sendSyncCmd("G01 Z{0}\n".format(wellHeight))
       robot.sendSyncCmd("G04 P1\n")
       # And dispense a fly
       dispenser.sendSyncCmd('F')
       print "Initial fly dispense, well #", self._currentWell
       dispensing = 1
       pCount=0
       # Loop here so we can process subsequent purge or dispense commands
       # with the same code
       while (dispensing == 1) and (pCount <= 3):
         print " pCount =", pCount
         r = ""
         while r == "":
           time.sleep(0.25)
           r = dispenser.getSerOutput()
         s = r.rstrip("\n\r")
         # Dispenser returns 'f' on successful dispense 
         if ( s == "f" ):
           print "  Fly dispensed."
           wx.PostEvent(self._notify_window, ResultEvent(self._currentWell+1))
           dispensing = 0
         elif ( s == "n" ):
           # Saw a fly come through sensor below wheels, but not
           # the dispenser pen. Try to purge.
           if ( pCount == 0 ) or ( pCount == 2):
             dispenser.sendSyncCmd('P')
             print "  No fly. Purge"
           elif ( pCount == 1 ):
             dispenser.sendSyncCmd('F')
             print "  No fly. Re-dispense"
         elif ( s == "t" ):
           # Timeout at the dispenser - no fly after 15 s
           # Try a few times
           # If we couldn't dispense a fly, break out
           if pCount < 2:
             dispenser.sendSyncCmd('F')
             print "  Timeout. Re-dispense"
           else:
             self._run_status = 0
             dispensing = -1
         else:
           print "  Received unexpected reply from dispenser:", s
           self._run_status = 0
           dispensing = -1
         pCount += 1
       print "Status - Dispensing =", dispensing, " and pCount=", pCount
       robot.sendSyncCmd("G01 Z{0}\n".format(clearanceHeight))
       if (dispensing == -1):
         break
       # Increment well counter
       self._currentWell += 1
       if ( self._currentWell > 95 ):
         break

    # If run status is 0, it's b/c dispenser failed
    if ( self._run_status == 0 ):
      wx.PostEvent(self._notify_window, ResultEvent(-(self._currentWell+1)))
    else:
      # Otherwise we're done. If we didn't quit, it means
      # we're also done with the whole plate (send event with data=None)
      if ( self._want_abort == 0 ) or ( self._currentWell > 95):
	robot.sendSyncCmd("G01 X0 Y40 Z{0}\n".format(clearanceHeight))
        wx.PostEvent(self._notify_window, ResultEvent(None))
      else:
        wx.PostEvent(self._notify_window, ResultEvent(-(self._currentWell+1)))
    return


  def abort(self):
    """abort worker thread."""
    # Method for use by main thread to signal an abort
    self._want_abort = 1

# Derive a new class for our main application window (Frame)
class LoaderFrame(wx.Frame):

  def __init__(self, parent, title):
    # State tracking information
    self.startState = 0
    self.currentWell = 0
    self.worker = None

    wx.Frame.__init__(self, parent, title=title, size=(800,480))
    self.SetBackgroundColour(wx.WHITE)

    # Keep track of the three icons
    self.emptyBitmap = wx.BitmapFromImage(
                        wx.Image("./Empty.png", wx.BITMAP_TYPE_PNG))
    self.redBitmap = wx.BitmapFromImage(
                        wx.Image("./Red.png", wx.BITMAP_TYPE_PNG))
    self.greenBitmap = wx.BitmapFromImage(
                        wx.Image("./Green.png", wx.BITMAP_TYPE_PNG))

    # We keep an array of the 96 bitmaps on screen so we can
    # change them later on.
    self.bmpArray = []
    box = wx.BoxSizer(wx.VERTICAL)
    # Add a little padding at the top
    box.AddSpacer(20)

    # Now build the 96 well plate representation on screen
    for i in range(8):
      hBox = wx.BoxSizer(wx.HORIZONTAL)
      for j in range(12):
        b = wx.StaticBitmap(self, bitmap=wx.EmptyBitmap(24, 24))
        t = wx.StaticText(self, size=wx.Size(28, 24),
                  label="{0}{1}".format(chr(i+ord('A')), j+1),
                  style=wx.ALIGN_RIGHT)
        b.SetBitmap(self.emptyBitmap)
        hBox.Add(t, 0, wx.ALL, 2)
        hBox.Add(b, 0, wx.ALL, 3)
        self.bmpArray.append(b)
      box.Add(hBox, 0, wx.ALL, 10)
    # Underneath the 96 well plate icons are three buttons
    hBox = wx.BoxSizer(wx.HORIZONTAL)
    self.startButton = wx.Button(self, label="Start")
    self.resetButton = wx.Button(self, label="Reset")
    self.quitButton = wx.Button(self, label="Quit")
    hBox.Add(self.startButton, 0, wx.ALL, 5)
    hBox.Add(self.resetButton, 0, wx.ALL, 5)
    hBox.AddSpacer(50)
    hBox.Add(self.quitButton, 0, wx.ALL, 5)
    box.Add(hBox, 0, wx.CENTER, 10)
    self.SetSizer(box)
    self.Layout()

    # Now bind some functions to the buttons and event notification
    self.startButton.Bind(wx.EVT_BUTTON, self.OnStart)
    self.resetButton.Bind(wx.EVT_BUTTON, self.OnReset)
    self.quitButton.Bind(wx.EVT_BUTTON, self.OnClose)
    EVT_RESULT(self,self.OnResult)

    #self.Show(True)
    self.ShowFullScreen(True)

  # Reset button callback
  def OnReset(self, event):
    self.currentWell = 0
    for i in range(len(self.bmpArray)):
      self.bmpArray[i].SetBitmap(self.emptyBitmap)
    self.startButton.SetLabel("Start")
    self.startButton.Enable()
    self.resetButton.Enable()
    self.quitButton.Enable()
    self.startState = 0
    self.worker = None

  # Start (or pause) button callback
  def OnStart(self, event):
    if ( self.startState == 0 ):
      self.startButton.SetLabel("Pause")
      self.resetButton.Disable()
      self.quitButton.Disable()
      self.startState = 1
      if not self.worker:
        self.worker = WorkerThread(self, start_val = self.currentWell )
    else:
      self.startButton.Disable()
      self.worker.abort()

  # Quit button callback
  def OnClose(self, event):
    dlg = wx.MessageDialog(self, "Exit PlateLoader?", "Confirm Exit",
                             wx.OK | wx.CANCEL | wx.ICON_QUESTION)
    result = dlg.ShowModal()
    dlg.Destroy()
    if result == wx.ID_OK:
      print "Wrapping up & closing serial ports."
      robot.sendSyncCmd("G28\n")
      robot.sendSyncCmd("M84\n")
      robot.close()
      dispenser.close()
      self.Destroy()

  # Callback for event sent from worker thread
  def OnResult(self, event):
    # Either we need to update an image
    # or other thread is done.
    if event.data is None:
      # Task completed
      self.startButton.Disable()
      self.resetButton.Enable()
      self.quitButton.Enable()
      self.worker = None
    elif event.data > 0:
      # Mark well as full
      self.bmpArray[event.data-1].SetBitmap(self.greenBitmap)
    else:
      # Mark well as empty, reset button states
      self.currentWell = (-event.data)-1
      self.bmpArray[-event.data-1].SetBitmap(self.redBitmap)
      self.startButton.SetLabel("Start")
      self.startButton.Enable()
      self.resetButton.Enable()
      self.quitButton.Enable()
      self.startState = 0
      self.worker = None


# Note that this index (i) is zero based.
# So getWell(0) returns coords for well A1
# getWell(1) returns coords for well A2
# ...
# and getWell(95) returns coords for well H12
def getWell(i):
  global majorBasis, minorBasis
  if ( i < 0 or i > 95 ):
    print "FlyPlate error: index out of bounds (", i, ")."
    return

  coords = startWellPoint + (int(i/12))*minorBasis + (i%12)*majorBasis
  return coords



# BEGIN PROGRAM

# (Due to printrboard config, well spacing is off by ~1%)
majorBasis = np.array([9.09, 0.])
minorBasis = np.array([0., -9.09])

# Some linear algebra to handle any rotation of the plate

# First, check the length of endWellPoint-startWellPoint
# against the nominal distance for sanity
l = np.linalg.norm(endWellPoint-startWellPoint)
nominalVect = 11*majorBasis + 7*minorBasis
nominalDist = np.linalg.norm( nominalVect)
if ( np.absolute( 1 - l / (nominalDist) ) > 0.01 ):
  print "FlyPlate warning: check coordinates. Length should be", (9.*np.sqrt(170.)), "but is", l

# Now calculate the angle between the actual coords and the axis-aligned coords
# reminder: a * b = |a| |b| cos(t)
#     and   a x b = |a| |b| sin(t)
#
# We solve for sin(t) and cos(t)
cosAngle = np.dot( (endWellPoint-startWellPoint),
                   nominalVect ) / ( l * nominalDist )
sinAngle = -np.cross( (endWellPoint-startWellPoint),
                   nominalVect ) / ( l * nominalDist )

# Construct the rotation matrix                               
rotMat = np.array( [ [cosAngle, -sinAngle], [ sinAngle, cosAngle] ])

# Now apply the rotation matrix to the basis vectors
majorBasis = rotMat.dot(majorBasis)
minorBasis = rotMat.dot(minorBasis)



# Search the available USB serial ports to find
# the dispenser and printrboard (running Marlin firmware)
portList = glob.glob('/dev/ttyACM*')
if len(portList) != 2:
  print "Port list should have exactly two items:", portList, len(portList)
  time.sleep(5)
  exit()

for p in portList:
  print "Trying port:", p
  tempPort = fsSerial.fsSerial(p)
  tempPort.sendCmd('V')
  time.sleep(1)
  r=tempPort.getSerOutput()
  if r.startswith("  V"):
    print "Port:", p, "is dispenser"
    dispenser = tempPort
    dispenser.ser.flushInput()
    time.sleep(1)
    dispenser.sendSyncCmd("I")
  else:
    print "Port:", p, "is assumed to be printrboard"
    robot = tempPort

# Home the robot
robot.sendSyncCmd("G28\n")
robot.sendSyncCmd("G01 F3000\n")

print "Ports configured. Starting GUI."

# Start the GUI. Note that the dispenser and robot are controlled
# in the worker thread class
app = wx.App(False)
frame = LoaderFrame(None, 'FlySorter Plate Loader')
app.MainLoop()

# The OnClose() function handles the cleanup
