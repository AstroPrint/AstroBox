# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import threading
import logging
import os
import time
import struct

from octoprint.events import eventManager, Events
from octoprint.util import getExceptionString

from makerbot_driver import GcodeAssembler
from makerbot_driver.errors import BuildCancelledError, ProtocolError, ExternalStopError, PacketTooBigError, BufferOverflowError, PacketLengthError
from makerbot_driver.Gcode.errors import UnrecognizedCommandError

class PrintJobS3G(threading.Thread):
	UPDATE_INTERVAL_SECS = 2

	def __init__(self, printer, currentFile):
		super(PrintJobS3G, self).__init__()

		self._logger = logging.getLogger(__name__)
		self._serialLogger = logging.getLogger('SERIAL')
		self._serialLoggerEnabled = self._serialLogger.isEnabledFor(logging.DEBUG)
		self._printer = printer
		self._file = currentFile
		self._canceled = False
		self._heatingPlatform = False
		self._heatingTool = False
		self._heatupWaitStartTime = 0
		self._currentZ = None
		self._lastLayerHeight = None
		self._currentLayer = None
		self.daemon = True


		# ~~~ From https://github.com/jetty840/ReplicatorG/blob/master/scripts/s3g-decompiler.py

		# Command table entries consist of:
		# * The key: the integer command code
		# * A tuple:
		#   * idx 0: the python struct description of the rest of the data,
		#            of a function that unpacks the remaining data from the
		#            stream
		#   * idx 1: either a format string that will take the tuple of unpacked
		#            data, or a function that takes the tuple as input and returns
		#            a string
		# REMINDER: all values are little-endian. Struct strings with multibyte
		# types should begin with "<".
		# For a refresher on Python struct syntax, see here:
		# http://docs.python.org/library/struct.html
		self.commandTable = {    
			129: "<iiiI",
			130: "<iii",
			131: "<BIH",
			132: "<BIH",
			133: "<I",
			134: "<B",
			135: self.parseWaitForToolAction,
			136: self.parseToolAction,
			137: "<B",
			138: "<H",
			#139: "<iiiiiI",
			139: self.parseQueueExtendedPoint,
			140: "<iiiii",
			141: self.parseWaitForPlatformAction,
			#142: "<iiiiiIB",
			142: self.parseQueueExtendedPointNew,
			143: "<b",
			144: "<b",
			145: "<BB",
			146: "<BBBBB",
			147: "<HHB",
			148: "<BHB",
			149: self.parseDisplayMessageAction,
			150: "<BB",
			151: "<B",
			152: "<B",
			153: self.parseBuildStartNotificationAction,
			154: "<B",
			#155: "<iiiiiIBfh",
			155: self.parseQueueExtendedPointX3g,
			156: "<B",
			157: "<BBBIHHIIB",
			158: "<f"
		}

	def cancel(self):
		self._canceled = True

	def run(self):
		profile = self._printer._profile

		self._printer._heatingUp = True
		self._printer.mcHeatingUpUpdate(True)
		self._heatupWaitStartTime = time.time()
		self._heatingTool = True
		self._lastLayerHeight = 0.0
		self._currentLayer = 0

		try:
			self._printer._comm.reset()
			self._printer._comm.build_start_notification(os.path.basename(self._file['filename'])[:15])
			self._printer._comm.set_build_percent(0)

			self._file['start_time'] = time.time()
			self._file['progress'] = 0

			lastProgressReport = 0
			lastProgressValueSentToPrinter = 0
			lastHeatingCheck = self._file['start_time']

			with open(self._file['filename'], 'rb') as f:
				while True:
					packet = bytearray()

					try:
						command = f.read(1)

						if self._canceled or len(command) == 0:
							break

						packet.append(ord(command))

						command = struct.unpack("B",command)
						try:
							parse = self.commandTable[command[0]]

						except KeyError:
							raise Exception("Unexpected packet type: 0x%x" % command[0])

						if type(parse) == type(""):
							packetLen = struct.calcsize(parse)
							packetData = f.read(packetLen)
							if len(packetData) != packetLen:
								raise Exception("Packet incomplete")
						else:
							packetData = parse(f)

						for c in packetData:
							packet.append(ord(c))

						if self.send_packet(packet):
							self._serialLoggerEnabled and self._serialLogger.debug('{"event":"packet_sent", "data": "%s"}' % ' '.join('0x{:02x}'.format(x) for x in packet) )

							now = time.time()
							if now - lastProgressReport > self.UPDATE_INTERVAL_SECS:
								position = f.tell()
								self._file['position'] = position
								self._file['progress'] = float(position) / float(self._file['size'])
								self._printer.mcProgress()

								printerProgress = int(self._file['progress'] * 100.0)

								if lastProgressValueSentToPrinter != printerProgress:
									try:
										self._printer._comm.set_build_percent(printerProgress)
										lastProgressValueSentToPrinter = printerProgress
										lastProgressReport = now

									except BufferOverflowError:
										time.sleep(.2)

							if self._printer._heatingUp and now - lastHeatingCheck > self.UPDATE_INTERVAL_SECS:
								lastHeatingCheck = now

								if  	( not self._heatingPlatform or ( self._heatingPlatform and self._printer._comm.is_platform_ready(0) ) )  \
									and ( not self._heatingTool or ( self._heatingTool and self._printer._comm.is_tool_ready(0) ) ):
								 
									self._heatingTool = False
									self._heatingPlatform = False
									self._printer._heatingUp = False
									self._printer.mcHeatingUpUpdate(False)
									self._heatupWaitTimeLost = now - self._heatupWaitStartTime
									self._heatupWaitStartTime = now
									self._file['start_time'] += self._heatupWaitTimeLost

					except ProtocolError as e:
						self._logger.warn('ProtocolError: %s' % e)

			self._printer._comm.build_end_notification()

			if self._canceled:
				self._printer._comm.clear_buffer()

			#Is possible to get a BufferOverflowError when succesfully completing a job
			continueEndSequence = False
			findAxesTries = 0
			while not continueEndSequence:
				try:
					self._printer._comm.find_axes_maximums(['x', 'y'], 200, 10)
					continueEndSequence = True

				except BufferOverflowError:
					if findAxesTries < 3:
						time.sleep(.2)
						findAxesTries += 1
					else:
						continueEndSequence = True

			#find current z:
			moveToPosition, endStopsStates = self._printer._comm.get_extended_position()
			zEndStopReached = endStopsStates & 16 == 16 #endstop is a bitfield. See https://github.com/makerbot/s3g/blob/master/doc/s3gProtocol.md (command 21)

			if zEndStopReached:

				#calculate Z max
				moveToPosition[2] = self._printer._profile.values['axes']['Z']['platform_length'] *  self._printer._profile.values['axes']['Z']['steps_per_mm']

				#move to the bottom:
				self._printer._comm.queue_extended_point_classic(moveToPosition, 100)

			self._printer._comm.toggle_axes(['x','y','z','a','b'], False)

			self._printer._changeState(self._printer.STATE_OPERATIONAL)

			payload = {
				"file": self._file['filename'],
				"filename": os.path.basename(self._file['filename']),
				"origin": self._file['origin'],
				"time": self._printer.getPrintTime(),
				"layerCount": self._currentLayer
			}

			if self._canceled:
				self._printer.printJobCancelled()
				eventManager().fire(Events.PRINT_FAILED, payload)
				self._printer._fileManager.printFailed(payload['filename'], payload['time'])

			else:
				self._printer.mcPrintjobDone()
				self._printer._fileManager.printSucceeded(payload['filename'], payload['time'], payload['layerCount'])
				eventManager().fire(Events.PRINT_DONE, payload)

		except BuildCancelledError:
			self._logger.warn('Build Cancel detected')
			self._printer.printJobCancelled()
			payload = {
				"file": self._file['filename'],
				"filename": os.path.basename(self._file['filename']),
				"origin": self._file['origin'],
				"time": self._printer.getPrintTime()
			}
			eventManager().fire(Events.PRINT_FAILED, payload)
			self._printer._fileManager.printFailed(payload['filename'], payload['time'])
			self._printer._changeState(self._printer.STATE_OPERATIONAL)

		except ExternalStopError:
			self._logger.warn('External Stop detected')
			self._printer._comm.writer.set_external_stop(False)
			self._printer.printJobCancelled()
			payload = {
				"file": self._file['filename'],
				"filename": os.path.basename(self._file['filename']),
				"origin": self._file['origin'],
				"time": self._printer.getPrintTime()
			}
			eventManager().fire(Events.PRINT_FAILED, payload)
			self._printer._fileManager.printFailed(payload['filename'], payload['time'])
			self._printer._changeState(self._printer.STATE_OPERATIONAL)			

		except Exception as e:
			self._errorValue = getExceptionString()
			self._printer._changeState(self._printer.STATE_ERROR)
			eventManager().fire(Events.ERROR, {"error": self._errorValue })
			self._logger.error(self._errorValue)

	def send_packet(self, data):
		while True:
			try:
				self._printer._comm.writer.send_action_payload(data)
				return True

			except BufferOverflowError:
				time.sleep(.2)

			except PacketTooBigError:
				self._logger.warn('Printer responded with PacketTooBigError to (%s)' % ' '.join('0x{:02x}'.format(x) for x in data))
				return False

			except UnrecognizedCommandError:
				self._logger.warn('The following command was ignored: %s' % ' '.join('0x{:02x}'.format(x) for x in data))
				return False

			except PacketLengthError as e:
				import makerbot_driver 

				if data[0] == makerbot_driver.constants.host_action_command_dict['BUILD_START_NOTIFICATION']:
					#we put out a warning here and ignore. There's a bug in the version of GPX that ships with Simplify 3D that allows
					#this command to go over the 32 bytes of max package
					self._logger.warn('Build name too long. Skipping Build Start Notification -  "%s"' % data[3:])
					return False

				raise e

	# ~~~ Slightly modified code for parsing from https://github.com/jetty840/ReplicatorG/blob/master/scripts/s3g-decompiler.py

	def parseToolAction(self, s3gFile):
		packetStr = s3gFile.read(3)
		if len(packetStr) != 3:
			raise Exception("Incomplete s3g file during tool command parse")
		(index,command,payload) = struct.unpack("<BBB",packetStr)
		contents = s3gFile.read(payload)
		if len(contents) != payload:
			raise Exception("Incomplete s3g file: tool packet truncated")
		return packetStr + contents

	def parseWaitForToolAction(self, s3gFile):
		packetLen = struct.calcsize("<BHH")
		packetData = s3gFile.read(packetLen)
		if len(packetData) != packetLen:
			raise Exception("Packet incomplete")

		if not self._printer._heatingUp:
			self._printer._heatingUp = True
			self._printer.mcHeatingUpUpdate(True)
			self._heatupWaitStartTime = time.time()

		self._heatingTool = True
		return packetData

	def parseWaitForPlatformAction(self, s3gFile):
		packetLen = struct.calcsize("<BHH")
		packetData = s3gFile.read(packetLen)
		if len(packetData) != packetLen:
			raise Exception("Packet incomplete")

		if not self._printer._heatingUp:
			self._printer._heatingUp = True
			self._printer.mcHeatingUpUpdate(True)
			self._heatupWaitStartTime = time.time()

		self._heatingPlatform = True
		return packetData

	def parseDisplayMessageAction(self, s3gFile):
		packetStr = s3gFile.read(4)
		if len(packetStr) < 4:
			raise Exception("Incomplete s3g file during tool command parse")
		message = "";
		while True:
		   	c = s3gFile.read(1);
			message += c;
			if c == '\0':
			  	break;

		return packetStr + message

	def parseBuildStartNotificationAction(self, s3gFile):
		packetStr = s3gFile.read(4)
		if len(packetStr) < 4:
			raise Exception("Incomplete s3g file during tool command parse")
		buildName = "";
		while True:
			c = s3gFile.read(1);
			buildName += c;
			if c == '\0':
				break;

		return packetStr + buildName

	def parseMovement(self, s3gFile, format):
		packetLen = struct.calcsize(format)
		packetData = s3gFile.read(packetLen)
		if len(packetData) != packetLen:
			raise Exception("Packet incomplete")

		unpacked = struct.unpack(format, buffer(packetData))

		if unpacked[2] != self._currentZ:
			self._currentZ = unpacked[2]
			self._printer.mcZChange(float(unpacked[2])/float(self._printer._profile.values['axes']['Z']['steps_per_mm']))
		elif self._currentZ != self._lastLayerHeight \
			and (unpacked[3] < 0 or unpacked[4] < 0): #add check for extrusion to avoid counting visited layers
			
			if self._currentZ > self._lastLayerHeight:
				self._currentLayer += 1
				self._printer.mcLayerChange(self._currentLayer)

			self._lastLayerHeight = self._currentZ

		return packetData, unpacked

	def parseQueueExtendedPoint(self, s3gFile):
		raw, unpacked = self.parseMovement(s3gFile, "<iiiiiI")
		return raw

	def parseQueueExtendedPointNew(self, s3gFile):
		raw, unpacked = self.parseMovement(s3gFile, "<iiiiiIB")
		return raw

	def parseQueueExtendedPointX3g(self, s3gFile):
		raw, unpacked = self.parseMovement(s3gFile, "<iiiiiIBfh")
		return raw
