# coding=utf-8
__author__ = "AstroPrint Product Team <product@astroprint.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 3DaGoGo, Inc - Released under terms of the AGPLv3 License"

import logging
import threading
import os
import time
import json

from sys import platform

from collections import deque

from .transport import TransportEvents


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# CommsListener: Callback interface for CommandsComms Users
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class CommsListener(object):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	# Implment these functions in the children class to respond to the events ~
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	#
	# Called when the link has been opened
	#
	def onLinkOpened(self):
		pass

	#
	# Called when the link has an error
	#
	def onLinkError(self, error, description= None):
		pass

	#
	# Called when the link has an info message (for example read_timeout)
	# You can't send from this function on the same thread or it will block the receiver
	#
	def onLinkInfo(self, info):
		pass

	#
	# Called when the link has been closed
	#
	def onLinkClosed(self):
		pass

	#
	# Called when a new response that wasn't handled bu a commmand is received from the printer
	#
	def onUnhandledResponse(self, command):
		pass

	#
	# A Signal has been found on the command Queue.
	#
	# - signal: PrintCompleted, PrintPaused, PrintCanceled
	#
	def onSignalReceived(self, signal):
		pass

	#
	# Called when a new data is sent to the printer
	#
	def onDataSent(self, data):
		pass

	#
	# Called when a new line is read from the file while an active print job is ongoing. Should process the line and return a list of command objects
	#
	# - line: The command read from the file
	#
	# - RETURN: an list containing the resulting command object sequence after the translation, or None if the line is to be ignored
	#
	def onFileLineRead(self, line):
		return None

	#
	# Called when the end of the current file has been reached
	#
	def onEndOfFle(self):
		pass

	#
	# Called when there's an error in an ogoing print job
	#
	def onJobError(self, error, description=None):
		pass

	#
	# Called when a status command needs to be sent. The implementing class should queue the appropiate commands
	#
	def onStatusCommandsNeeded(self):
		pass

	#
	# Called when a job progress is reported
	#
	def onPrintJobProgress(self, percentCompleted, filePos):
		pass





# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Command Pluging Events and requests   ~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class CommandPluginInterface(object):
	# ~~~~~~~~~~~~~ Data Requests ~~~~~~

	#
	# Returns a type PrinterState with the current state of the printer
	#
	@property
	def printerState(self):
		raise NotImplementedError()

	#
	# Returns the current Z value
	#
	@property
	def currentZ(self):
		raise NotImplementedError()

	#
	# Returns the last known layer height
	#
	@property
	def lastLayerHeight(self):
		raise NotImplementedError()

	# ~~~~~~~~~~~~~ Events ~~~~~~~~~~~~~

	#
	# Called when a heat and wait command is sent to the printer
	#
	def onWaitForTemperature(self):
		pass

	#
	# Called when a Z movement command is detected
	#
	def onZMovement(self, currentZ):
		pass

	#
	# Called when a Z movement command is detected
	#
	def onZMovement(self, currentZ):
		pass

	#
	# Called when first Extrusion is detected after the last Z Movement
	#
	def onExtrusionAfterZMovement(self):
		pass

	#
	# Called when the extrusion mode changes
	#
	# - mode: a value from MaterialCounter: EXTRUSION_MODE_ABSOLUTE or EXTRUSION_MODE_RELATIVE
	#
	def onExtrusionModeChanged(self, mode):
		pass

	#
	# Called when the extrusion length is reset
	#
	# - value: The value to which is reset
	#
	def onExtrusionLengthReset(self, value):
		pass

	#
	# Called when extrusion is detected
	#
	# - value: mm of filament extruded
	#
	def onExtrusion(self, value):
		pass

	#
	# Called when a new tool is selected
	#
	# - tool: The id of the new tool selected
	#
	def onToolChanged(self, tool):
		pass

	#
	# Called when printing speed is changed
	#
	# - amount: The speed in percentage
	#
	def onPrintingSpeedChanged(self, amount):
		pass

	#
	# Called when printing flow is changed
	#
	# - amount: The flow in percentage
	#
	def onPrintingFlowChanged(self, amount):
		pass

	#
	# Called when a command was sent that requests current position
	#
	def onCurrentPositionRequested(self):
		pass







# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Command: Base class for the command object
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class Command(object):
	def __init__(self, command):
		self._command = command
		self._encoded = None
		self._completed = False
		self._received = False
		self.isQueued = False #Indicates that the command is queued

	def __eq__(self, otherCmd):
		return otherCmd == self._command

	#
	# This function is called when the command is ready to be put in the command
	#
	@property
	def command(self):
		return self._command

	#
	# Returns the encoded command as it's supposed to be sent over to the printer
	#
	@property
	def encodedCommand(self):
		if self._encoded is None:
			self._encoded = self.doEncodeCommand()

		return self._encoded

	@property
	def received(self):
		return self._received

	@property
	def completed(self):
		return self._completed

	#
	# Force and encode command. This is called right after adding the command to the queue
	#
	def encode(self):
		self._encoded = self.doEncodeCommand()

	# Implements these functions if the default is not enough

	#
	# Do the translating of the command and potentially split in several other commands
	#
	# Returns: a list of commands to be put in the queue, False if there's no translation, or None if the command sholdn't be put in the queue
	#
	def translateCommand(self):
		return False # Means the command doesn't change
		#return None # Means the command shouldn't be put in the queue

	#
	# Do the actual encode implementation
	#
	# Returns: the encoded command
	#
	def doEncodeCommand(self):
		return self._command

	#
	# Called just before the command is going to be sent to the printer
	#
	# Returns: False if you want to stop the send
	#
	def onBeforeCommandSend(self):
		return True

	#
	# Implement what happens when the command was sent to the printer
	#
	def onCommandSent(self):
		pass

	#
	# Implement what should happen when the command is about to be added to the queue
	#
	# Return: False if you want to stop the send
	#
	def onBeforeCommandAddToQueue(self):
		return True

	#
	# Implement what should happen when the command is added to the command queue
	#
	def onCommandAddedToQueue(self):
		pass

	#
	# Implement what should happen when responses are retrieved after sending this command
	#
	def onResponse(self):
		raise NotImplementedError()



# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Signal: Class for signal objects
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class Signal(Command):
	def __init__(self, signalType, data):
		super(Signal, self).__init__(None)

		self._type = signalType
		self._data = data

	@property
	def type(self):
		return self._type

	@property
	def data(self):
		return self._data






# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# CommandsComms: Helper class for command based communications protocols
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class CommandsComms(TransportEvents):
	def __init__(self, transport, listener):
		self._listener = listener
		self._logger = logging.getLogger(self.__class__.__name__)
		self._serialLogger = logging.getLogger("SERIAL")
		self._serialLoggerEnabled = self._serialLogger.isEnabledFor(logging.DEBUG)
		self._statusPoller = None
		self._printJob = None
		self._sender = None

		if transport == 'serial':
			from .transport.serial_t import SerialCommTransport
			self._transport = SerialCommTransport(self)

		elif transport == 'usb':
			from .transport.usb_t import UsbCommTransport
			self._transport = UsbCommTransport(self)

		else:
			raise "Invalid transport %s" % transport

	def __del__(self):
		self._logger.debug('Object Removed')
		self.closeLink()

	#
	# Closes the link and performs cleanup
	#
	def closeLink(self):
		if self.printing:
			self.stopPrint()

		self.stopStatusPoller()
		self.stopSender()
		self._transport.closeLink()

	#
	# Return the transport object
	#
	@property
	def transport(self):
		return self._transport

	#
	# Whether the link is open or not
	#
	@property
	def isLinkOpen(self):
		return self._transport.isLinkOpen


	#
	# Whether the link is valid and can still be used to send/receive data
	#
	@property
	def canLinkTransmit(self):
		return self._transport.canTransmit


	#
	# Return the settings of the active connection. (port, baudrate)
	#
	@property
	def connectionSettings(self):
		return self._transport.connSettings

	#
	# Returns whether there's an active print job
	#
	@property
	def printing(self):
		return self._printJob is not None

	#
	# Returns the number of commands in queue
	#
	@property
	def commandsInQueue(self):
		return self._sender.commandsInQueue if self._sender else 0

	#
	# Inidicates whether serial logs is enabled
	#
	@property
	def serialLogEnabled(self):
		return self._serialLoggerEnabled

	#
	# Add the commands to the send queue
	#
	def queueCommands(self, commands, sendNext= False):
		if self._sender:
			self._sender.addCommands(commands, sendNext)

	#
	# Add the commmand to the send queue
	#
	def queueCommand(self, command, sendNext= False):
		if self._sender:
			self._sender.addCommands([command], sendNext)

	#
	#	Send the command inmediately
	#
	def sendCommand(self, command):
		if self._sender:
			self._sender.sendCommand(command)

	#
	# Add a Signal to the Queue. They're send back via the onSignalReceived
	#
	def queueSignal(self, signal, data=None ):
		if self._sender:
			self._sender.addCommands([Signal(signal, data)])

	#
	# Add a command to the queue if it's not already there
	#
	def queueCommandIfNotExists(self, command, sendNext= False):
		if self._sender:
			self._sender.addCommandIfNotExists(command, sendNext)

	#
	# Report that the serial logging has changed
	#
	def serialLoggingChanged(self):
		self._serialLoggerEnabled = self._serialLogger.isEnabledFor(logging.DEBUG)

	#
	# Sends next command in queue
	#
	def sendNextCommandInQueue(self):
		if self._sender:
			self._sender.sendNext()

	#
	# Indicates to the sender that it can send the next command it gets in the queue
	#
	def setReadytoSend(self):
		if self._sender:
			self._sender.setReadytoSend()

	#
	# write 'data' on the underlying link
	#
	def writeOnLink(self, data, completed= None):
		if data is not None:
			def sendCompleted():
				self._serialLoggerEnabled and self.writeToSerialLog('S: %r' % data)
				if completed:
					completed()

				self._listener.onDataSent(data)

			self._transport.write(data, sendCompleted)

	#
	# Starts status poller
	#
	def startStatusPoller(self, interval=5.0):
		if not self._statusPoller:
			self._statusPoller = StatusPoller(self._listener, interval)
			self._statusPoller.start()

	#
	# Stops the status poller
	#
	def stopStatusPoller(self):
		if self._statusPoller:
			self._statusPoller.stop()
			self._statusPoller = None

	#
	# Starts sender
	#
	def startSender(self):
		if not self._sender:
			self._sender = CommandSender(self, self._listener)

	#
	# Stops the sender
	#
	def stopSender(self):
		if self._sender:
			self._sender = None

	#
	# Set Paused of the status poller
	#
	def setStatusPollerPaused(self, paused):
		if self._statusPoller:
			self._statusPoller.paused = paused

	#
	# Starts printing 'filename'
	#
	def startPrint(self, filename):
		if not self._printJob:
			self._printJob = JobWorker(filename, self, self._listener)
			self._printJob.start()

	#
	# Enqueues commands from file into the printing queue
	#
	# - count: Number of commands to read
	#
	def readCommandsFromFile(self, count):
		if self._printJob:
			self._printJob.read(count)

	#
	# Stops current print
	#
	def stopPrint(self):
		if self._printJob:
			self._printJob.stop()
			self._printJob = None
			if self._sender:
				self._sender.clearCommandQueue()

	#
	# Pauses the current print job
	#
	def pausePrintJob(self):
		if self._printJob and self._sender:
			self._sender.storeCommands()

	#
	# Resumes the current print job
	#
	def resumePrintJob(self):
		if self._printJob and self._sender:
			self._sender.restoreCommands()

	#
	# Writes to serial logs if enabled
	#
	def writeToSerialLog(self, message):
		self._serialLogger.debug(message)

	#
	# Returns a response that was consumed back to be processed again
	#
	def injectCommandResponse(self, data):
		if self._sender:
			self._sender.onCommandResponse(data)


	#~~~~~~~~~~~~~~~~~~~~~~~~~
	# Events from Job Worker ~
	#~~~~~~~~~~~~~~~~~~~~~~~~~

	def onEndOfFle(self):
		self._printJob = None
		self._listener.onEndOfFle()

	# ~~~~~~~~~~~~~~~~~
	# TransportEvents ~
	# ~~~~~~~~~~~~~~~~~

	def onDataReceived(self, data):
		self._serialLoggerEnabled and self.writeToSerialLog('R: %r' % data)

		if self._sender:
			self._sender.onCommandResponse(data)

	def onLinkError(self, error, description= None):
		self._listener.onLinkError(error, description)
		self._transport.closeLink()

	def onLinkClosed(self):
		self._listener.onLinkClosed()

	def onLinkOpened(self):
		self.startSender()
		self._listener.onLinkOpened()

	def onLinkInfo(self, info):
		self._listener.onLinkInfo(info)
		self._serialLoggerEnabled and self.writeToSerialLog(info)


#~~~~~~ Worker to read commands from file

class JobWorker(threading.Thread):
	_reportProgressInterval = 1.0

	def __init__(self, filename, comm, eventListener): #eventListener is object of interface CommsListener
		super(JobWorker, self).__init__()
		self._logger = logging.getLogger(self.__class__.__name__)
		self._filename = filename
		self._comm = comm
		self._eventListener = eventListener
		self._stopped = False
		self._fileHandler = None
		self._fileSize = None
		self._readEvent = threading.Event()
		self._lastReport = None

	def run(self):
		while not self._stopped:
			if ( time.time() - self._lastReport ) >= self._reportProgressInterval:
				filePos = self.filePos
				percent = filePos / self._fileSize
				self._eventListener.onPrintJobProgress( percent, filePos )
				self._lastReport = time.time()

			self._readEvent.wait()
			addedCommands = 0
			while not self._stopped:
				line = self._fileHandler.readline()
				if line == '':
					# end of file reached
					self.stop()
					self._comm.onEndOfFle()

				else:
					try:
						commandObjs = self._eventListener.onFileLineRead(line)
					except:
						commandObjs = None
						self._logger.error('Error processing job command', exc_info= True)
						self._eventListener.onJobError("error_processing_command")

					if commandObjs is not None:
						self._comm.queueCommands( commandObjs )
						addedCommands += len(commandObjs)

						if addedCommands >= self._maxCommands:
							self._readEvent.clear()
							break

	def stop(self):
		if not self._stopped:
			self._stopped = True
			self._readEvent.set()
			self._fileHandler.close()
			self._fileHandler = None

	def start(self):
		#open the file
		self._fileHandler = open(self._filename, 'r')
		self._readEvent.clear()
		self._fileSize = float(os.stat(self._filename).st_size)
		self._eventListener.onPrintJobProgress(0.0, 0)
		self._lastReport = time.time()

		super(JobWorker, self).start()

	def read(self, maxCommands):
		self._maxCommands = maxCommands
		self._readEvent.set()

	@property
	def filePos(self):
		if self._fileHandler:
			return self._fileHandler.tell()
		else:
			return None

#~~~~~~ Worker to request status from the printer

class StatusPoller(threading.Thread):
	def __init__(self, eventListener, interval=5.0):
		super(StatusPoller, self).__init__()
		self._stopped = False
		self._interval = interval
		self._eventListener = eventListener
		self._event = threading.Event()
		self._pauseEvent = threading.Event()
		self._pauseEvent.set()

	def run(self):
		while not self._stopped:
			self._eventListener.onStatusCommandsNeeded()
			self._event.wait(self._interval)
			self._pauseEvent.wait()

	def stop(self):
		self._stopped = True
		self._pauseEvent.set()
		self._event.set()

	@property
	def paused(self):
		return not self._pauseEvent.is_set()

	@paused.setter
	def paused(self, paused):
		if paused:
			self._pauseEvent.clear()
		else:
			self._pauseEvent.set()

#~~~~~~ Worker to empty the command queue

#class CommandSender(threading.Thread):
class CommandSender(object):
	def __init__(self, comms, eventListener):
		self._logger = logging.getLogger(self.__class__.__name__)
		self._stopped = False
		self._eventListener = eventListener
		self._comms = comms
		self._commandQ = deque()
		self._readyToSend = True
		self._storedCommands = None
		self._pendingCommands = deque()
		self._pendingCommmandsLock = threading.RLock()

	def fireNextCommand(self):
		self._readyToSend = False

		try:
			command = self._commandQ.pop()

		except IndexError:
			self._readyToSend = True
			return

		if command:
			if isinstance(command, Signal):
				#This is a signal placed in the queue, we tell the event listener and move on
				self._eventListener.onSignalReceived( command.type, command.data )
				self.fireNextCommand()

			elif isinstance(command, Command):
				self.sendCommand(command)

			else:
				self._logger.warn("The following invalid command type was found in the queue: %r" % command)


	def sendCommand(self, command):
		if command.onBeforeCommandSend() is not False:
			try:
				self._comms.writeOnLink(command.encodedCommand, command.onCommandSent)
				with self._pendingCommmandsLock:
					self._pendingCommands.appendleft(command)

			except Exception as e:
				self._eventListener.onLinkError('unable_to_send', "Error: %s, command: %s" % (e, command.command))

		else:
			self.sendNext()

	def onCommandResponse(self, data):
		if data:
			try:
				data = data.decode('ascii').strip()

				toBeRemoved = None
				sendNext = False
				handled = False

				with self._pendingCommmandsLock:
					pc = list(self._pendingCommands)

				for c in pc:
					if c.onResponse(data):
						if c.completed:
							toBeRemoved = c

							if c.isQueued:
								sendNext = True

						handled = True
						break

				if not handled:
					self._eventListener.onUnhandledResponse(data)

				if toBeRemoved:
					with self._pendingCommmandsLock:
						self._pendingCommands.remove(toBeRemoved)

				if sendNext:
					self.sendNext()

			except:
				self._logger.error('Error handling data received.', exc_info= True)

	def storeCommands(self):
		self._storedCommands = list(self._commandQ)
		self._commandQ.clear()

	def restoreCommands(self):
		if self._storedCommands:
			self._commandQ.extend(self._storedCommands)
			self._storedCommands = None

	def sendNext(self):
		if self._readyToSend:
			sendAllowed = True
		else:
			with self._pendingCommmandsLock:
				sendAllowed = all([( not c.isQueued ) for c in self._pendingCommands])

		if sendAllowed:
			self.fireNextCommand()

	def setReadytoSend(self):
		self.sendNext()

	def addCommands(self, commands, sendNext= False):
		if commands:
			toBeDeleted = []

			for c in commands:
				if not c.onBeforeCommandAddToQueue():
					toBeDeleted.append(c)

				for c in toBeDeleted:
					commands.remove(c)

			commandCount = len(commands)

			if commandCount:
				if sendNext:
					self._commandQ.extend(commands)
				else:
					self._commandQ.extendleft(commands)

				for c in commands:
					c.encode()
					c.isQueued = True
					c.onCommandAddedToQueue()

				if self._readyToSend or len(self._commandQ) == commandCount:
					self.sendNext()

	def addCommandIfNotExists(self, command, sendNext= False):
		if command not in self._commandQ:
			self.addCommands([command], sendNext)

	def clearCommandQueue(self):
		self._commandQ.clear()
		with self._pendingCommmandsLock:
			self._pendingCommands.clear()

	@property
	def commandsInQueue(self):
		return len(self._commandQ)
