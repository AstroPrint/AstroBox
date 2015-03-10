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
from makerbot_driver.errors import BuildCancelledError, ProtocolError, ExternalStopError, PacketTooBigError, BufferOverflowError
from makerbot_driver.Gcode import GcodeParser
from makerbot_driver.Gcode.errors import UnrecognizedCommandError

class PrintJobS3G(threading.Thread):
	UPDATE_INTERVAL_SECS = 2

	def __init__(self, printer, currentFile):
		super(PrintJobS3G, self).__init__()

		self._logger = logging.getLogger(__name__)
		self._printer = printer
		self._file = currentFile
		self._canceled = False
		self._heatingPlatform = False
		self._heatingTool = False
		self._heatupWaitStartTime = 0
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
			139: "<iiiiiI",
			140: "<iiiii",
			141: self.parseWaitForPlatformAction,
			142: "<iiiiiIB",
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
			155: "<iiiiiIBfh",
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

		try:
			assembler = GcodeAssembler(profile)
			start, end, variables = assembler.assemble_recipe()
			start_gcode = assembler.assemble_start_sequence(start)
			end_gcode = assembler.assemble_end_sequence(end)

			variables.update({
				'START_X': profile.values['print_start_sequence']['start_position']['start_x'],
				'START_Y': profile.values['print_start_sequence']['start_position']['start_y'],
				'START_Z': profile.values['print_start_sequence']['start_position']['start_z']
			})

			self._parser = GcodeParser()
			self._parser.environment.update(variables)
			self._parser.state.set_build_name(os.path.basename(self._file['filename'])[:15])
			self._parser.state.profile = profile
			self._parser.s3g = self._printer._comm

			self._printer._comm.reset()

			#self._parser.state.values['last_extra_index'] = 0
			#self._parser.state.values['last_platform_index'] = 0

			if self._printer._firmwareVersion >= 700:
				vid, pid = self._printer._comm.get_vid_pid_iface()
				self._parser.s3g.x3g_version(1, 0, pid=pid) # Currently hardcode x3g v1.0

			for line in start_gcode:
				self.exec_gcode_line(line)

			self.exec_gcode_line('G1 X0 Y0 Z0')

			self._file['start_time'] = time.time()
			self._file['progress'] = 0

			lastProgressReport = 0
			lastProgressValueSentToPrinter = 0
			lastHeatingCheck = 0

			with open(self._file['filename'], 'rb') as f:
				while True:
					packet = bytearray()

					try:
						command = f.read(1)

						if self._canceled or len(command) == 0:
							break

						packet.append(ord(command))

						(command) = struct.unpack("B",command)
						parse = self.commandTable[command[0]]
						if type(parse) == type(""):
							packetLen = struct.calcsize(parse)
							packetData = f.read(packetLen)
							if len(packetData) != packetLen:
								raise "Packet incomplete"
						else:
							packetData = parse(f)

						for c in packetData:
							packet.append(ord(c))

						if self.send_packet(packet):
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

			if self._canceled:
				self._printer._comm.build_end_notification()

			else:
				for line in end_gcode:
					self.exec_gcode_line(line)

			self._printer._changeState(self._printer.STATE_OPERATIONAL)

			payload = {
				"file": self._file['filename'],
				"filename": os.path.basename(self._file['filename']),
				"origin": self._file['origin'],
				"time": self._printer.getPrintTime()
			}

			if self._canceled:
				self._printer.printJobCancelled()
				eventManager().fire(Events.PRINT_FAILED, payload)
			else:
				self._printer.mcPrintjobDone()
				eventManager().fire(Events.PRINT_DONE, payload)

		except BuildCancelledError:
			self._logger.warn('Build Cancel detected')
			self.cancel()
			self._printer.printJobCancelled()
			eventManager().fire(Events.PRINT_FAILED, payload)

		except ExternalStopError:
			self._logger.warn('External Stop detected')
			self.cancel()
			self._printer._comm.writer.set_external_stop(False)
			self._printer.printJobCancelled()
			eventManager().fire(Events.PRINT_FAILED, payload)

		except Exception:
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
				self._logger.warn('Printer responded with PacketTooBigError to (%s)' % line)
				return False

			except UnrecognizedCommandError:
				self._logger.warn('The following GCode command was ignored: %s' % line)
				return False

	def exec_gcode_line(self, line):
		print line
		while True:
			try:
				self._parser.execute_line(line)
				return True

			except BufferOverflowError:
				time.sleep(.2)

			except PacketTooBigError:
				self._logger.warn('Printer responded with PacketTooBigError to (%s)' % line)
				return False

			except UnrecognizedCommandError:
				self._logger.warn('The following GCode command was ignored: %s' % line)
				return False

	# ~~~ Slightly modified code for parsing from https://github.com/jetty840/ReplicatorG/blob/master/scripts/s3g-decompiler.py

	def parseToolAction(self, s3gFile):
		packetStr = s3gFile.read(3)
		if len(packetStr) != 3:
			raise "Incomplete s3g file during tool command parse"
		(index,command,payload) = struct.unpack("<BBB",packetStr)
		contents = s3gFile.read(payload)
		if len(contents) != payload:
			raise "Incomplete s3g file: tool packet truncated"
		return packetStr + contents

	def parseWaitForToolAction(self, s3gFile):
		packetLen = struct.calcsize("<BHH")
		packetData = s3gFile.read(packetLen)
		if len(packetData) != packetLen:
			raise "Packet incomplete"

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
			raise "Packet incomplete"

		if not self._printer._heatingUp:
			self._printer._heatingUp = True
			self._printer.mcHeatingUpUpdate(True)
			self._heatupWaitStartTime = time.time()

		self._heatingPlatform = True
		return packetData

	def parseDisplayMessageAction(self, s3gFile):
		packetStr = s3gFile.read(4)
		if len(packetStr) < 4:
			raise "Incomplete s3g file during tool command parse"
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
			raise "Incomplete s3g file during tool command parse"
		buildName = "";
		while True:
			c = s3gFile.read(1);
			buildName += c;
			if c == '\0':
				break;

		return packetStr + buildName
