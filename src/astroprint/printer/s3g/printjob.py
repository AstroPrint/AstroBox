# coding=utf-8
__author__ = "Daniel Arroyo <daniel@astroprint.com>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

import threading
import logging
import os
import time
import re


from octoprint.events import eventManager, Events
from octoprint.util import getExceptionString

from makerbot_driver import BufferOverflowError, GcodeAssembler
from makerbot_driver.errors import BuildCancelledError
from makerbot_driver.Gcode import GcodeParser
from makerbot_driver.Gcode.errors import UnrecognizedCommandError

class PrintJobS3G(threading.Thread):
	UPDATE_INTERVAL_SECS = 2

	def __init__(self, printer, currentFile):
		super(PrintJobS3G, self).__init__()

		self._printer = printer
		self._file = currentFile
		self._parser = None
		self._canceled = False
		self._heatingPlatform = False
		self._heatingTool = False
		self._heatupWaitStartTime = 0
		self.daemon = True
		self._regex_command = re.compile("^\s*([GM]\d+|T)")

	def exec_line(self, line):
		while True:
			try:
				self._parser.execute_line(line)
				break

			except BufferOverflowError as e:
				time.sleep(.2)

			except UnrecognizedCommandError as e:
				logging.warn(e)
				break

			except BuildCancelledError:
				logging.warn("print job cancelled by bot")
				self._canceled = True
				break

	def cancel(self):
		self._canceled = True

	def run(self):
		profile = self._printer._profile

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
			self._parser.state.values["build_name"] = os.path.basename(self._file['filename'])[:15]
			self._parser.state.profile = self._printer._profile
			self._parser.s3g = self._printer._comm

			for line in start_gcode:
				line = self._preprocessGcode(line)

				if line is not None:
					self.exec_line(line)

			self._file['start_time'] = time.time()
			self._file['progress'] = 0

			lastProgressReport = 0
			lastProgressValueSentToPrinter = 0
			lastHeatingCheck = 0

			with open(self._file['filename'], 'r') as f:
				while True:
					line = f.readline()

					if self._canceled:
						break

					if not line:
						break

					line = self._preprocessGcode(line)
					if line is not None:
						self.exec_line(line)

						now = time.time()
						if now - lastProgressReport > self.UPDATE_INTERVAL_SECS:
							position = f.tell()
							self._file['position'] = position
							self._file['progress'] = float(position) / float(self._file['size'])
							self._printer.mcProgress()

							printerProgress = int(self._file['progress'] * 100.0)

							if lastProgressValueSentToPrinter != printerProgress:
								try:
									self._parser.s3g.set_build_percent(printerProgress)
									lastProgressValueSentToPrinter = printerProgress

								except BufferOverflowError:
									time.sleep(.2)

							lastProgressReport = now

						if self._printer._heatingUp and now - lastHeatingCheck > self.UPDATE_INTERVAL_SECS:
							lastHeatingCheck = now

							try:
								if  	( not self._heatingPlatform or ( self._heatingPlatform and self._parser.s3g.is_platform_ready(0) ) )  \
									and ( not self._heatingTool or ( self._heatingTool and self._parser.s3g.is_tool_ready(0) ) ):
								 
									self._heatingTool = False
									self._heatingPlatform = False
									self._printer._heatingUp = False
									self._printer.mcHeatingUpUpdate(False)
									self._heatupWaitTimeLost = now - self._heatupWaitStartTime
									self._heatupWaitStartTime = now
									self._file['start_time'] += self._heatupWaitTimeLost

							except BufferOverflowError:
								time.sleep(.2)

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

			for line in end_gcode:
				line = self._preprocessGcode(line)

				if line is not None:
					self.exec_line(line)

		except:
			self._errorValue = getExceptionString()
			self._printer._changeState(self._printer.STATE_ERROR)
			eventManager().fire(Events.ERROR, {"error": self._errorValue })

	# ~~~ GCODE handlers

	def _preprocessGcode(self, cmd):
		gcode = self._regex_command.search(cmd)
		if gcode:
			gcode = gcode.group(1)

			gcodeHandler = "_handleGcode_" + gcode
			if hasattr(self, gcodeHandler):
				cmd = getattr(self, gcodeHandler)(cmd)

		return cmd

	def _handleGcode_M104(self, cmd):
		self._printer._heatingUp = True
		self._printer.mcHeatingUpUpdate(True)
		self._heatingTool = True
		self._heatupWaitStartTime = time.time()
		return cmd

	def _handleGcode_M109(self, cmd):
		self._printer._heatingUp = True
		self._printer.mcHeatingUpUpdate(True)
		self._heatingPlatform = True
		self._heatupWaitStartTime = time.time()
		return cmd

	# These Gcodes are ignored by the parser so cut them off here
	def _handleGcode_G90(self, cmd):
		return None

	def _handleGcode_G21(self, cmd):
		return None

	def _handleGcode_M106(self, cmd):
		return None
