#! /usr/bin/env python

## Copyright (c) 2016, FlySorter, LLC
#
# 

import numpy as np
import sys
import glob
import fsSerial
import time

# Configuration parameters

robotPort = '/dev/ttyACM0'
dispenserPort = '/dev/ttyACM1'
startWellPoint = np.array([-49.25, 31.0])
endWellPoint = np.array([50.75, -33.0])

clearanceHeight = 30.
wellHeight = 19

# End configuration parameters



wellSpacing = 9.
majorBasis = np.array([9.09, 0.])
minorBasis = np.array([0., -9.09])


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
cosAngle = np.dot(   (endWellPoint-startWellPoint), nominalVect ) / ( l * nominalDist )
sinAngle = -np.cross( (endWellPoint-startWellPoint), nominalVect ) / ( l * nominalDist )

#print "cos(t) =", cosAngle, "and sin(t) =", sinAngle

# Construct the rotation matrix                               
rotMat = np.array( [ [cosAngle, -sinAngle], [ sinAngle, cosAngle] ])

# Now apply the rotation matrix to the basis vectors
majorBasis = rotMat.dot(majorBasis)
minorBasis = rotMat.dot(minorBasis)


# Note that this index (i) is zero based.
# So getWell(0) returns coords for well A1
# getWell(1) returns coords for well A2
# ...
# and getWell(95) returns coords for well H12
def getWell(i):
	if ( i < 0 or i > 95 ):
		print "FlyPlate error: index out of bounds (", i, ")."
		return

	coords = startWellPoint + (int(i/12))*minorBasis + (i%12)*majorBasis
	return coords


portList = glob.glob('/dev/ttyACM*')
if len(portList) != 2:
	print "Port list should have exactly two items:", portList, len(portList)
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

print "Well height:", wellHeight

robot.sendSyncCmd("G28\n")
robot.sendSyncCmd("G01 F3000\n")
robot.sendSyncCmd("G01 Z{0}\n".format(clearanceHeight))

for i in range(96):
	wellCoords = getWell(i)
	robot.sendSyncCmd("G01 X{0} Y{1}\n".format(wellCoords[0], wellCoords[1]))
	robot.sendSyncCmd("G01 Z{0}\n".format(wellHeight))
	robot.sendSyncCmd("G04 P1\n")
	dispenser.sendSyncCmd('F')
	r = ""
	while r == "":
		time.sleep(0.25)
		r = dispenser.getSerOutput()
	s = r.rstrip("\n\r")
	print "Dispenser reply:", s
	if ( s == "f" ):
		print "Dispensed fly", i
	else:
		print "Failed to dispense fly."
		break
	robot.sendSyncCmd("G01 Z{0}\n".format(clearanceHeight))


robot.sendSyncCmd("G28\n")

robot.close()
dispenser.close()

