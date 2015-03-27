from __future__ import absolute_import

import re

from . import Processor
import makerbot_driver


class DualRetractProcessor(Processor):
    def __init__(self):
        super(DualRetractProcessor, self).__init__()
        self.layer_start = re.compile("^(;\s?Slice|\(<layer>) [0-9.]+.*", re.I)
        self.snort = re.compile(
            "^G1.*[AB]([0-9.-]+).*;? (?:Retract|End of print)|^G1 F[0-9.-]+\nG1 E([0-9.-]+)", re.I)
        self.squirt = re.compile(
            "^G1.*[AB]([0-9.-]+).*;? Restart|^G1 F[0-9.-]+\nG1 E([0-9.-]+)", re.I)
        self.toolchange = re.compile("^M135 T([0-9])")
        self.SF_feedrate = re.compile("^G1 F[0-9.-]+\n")
        self.prime = re.compile(".*prime.*|.*Prime.*")

        self.TOOLHEADS = ['A', 'B']


    def isGenerator(self,iterable):
        """
        Fucntion decides if the input iterable is a generator

        @param iterable: iterable object
        @return boolean: True if it is a generator
        """
        return hasattr(iterable, '__iter__') and not hasattr(iterable, '__len__')


    def sandwich_iter(self, iterable):
        """
        This function returns an iterator with the previous,current,and next values
        in a given iterable

        @param iterable: iterable object
        @return iterator of triplets
        """
        if(self.isGenerator(iterable)):
            iterator = iterable
        else:
            iterator = iter(iterable)

        current = iterator.next()
        prev = None

        for next in iterator:
            yield(prev,current,next)
            prev = current        
            current = next
        yield(prev,current,'')


    def process_gcode(self, gcode_in, gcode_info=None):
        """
        This function adds retractions and squirt tweaks to a gcode input

        @param gcode_in: iterable object containing gcode
        """
        self.retract_distance_mm = self.profile.values["dualstrusion"][
            "retract_distance_mm"]
        self.squirt_reduction_mm = self.profile.values["dualstrusion"][
            "squirt_reduce_mm"]
        self.squirt_feedrate = self.profile.values["dualstrusion"][
            "squirt_feedrate"]
        self.snort_feedrate = self.profile.values["dualstrusion"][
            "snort_feedrate"]


        if(self.retract_distance_mm == 0 or (not self.profile_supports_processor())):
            #If self.retract_distance_mm is NULL or 0 then don't run the processor on
            #the gcode
            for code in gcode_in:
                yield code
            raise StopIteration

        self.current_tool = -1
        self.last_tool = -1
        self.last_snort = {'index': None, 'tool': None, 'extruder_position':None}
        self.squirt_extruder_pos = None
        self.seeking_first_toolchange = True
        self.seeking_first_layer = True
        self.seeking_squirt = False
        self.SF_flag = False
        self.SF_handle_second_squirt_line = False
        self.buffer = []
        self.buffering = True
        self.flush_buffer = False

        for (previous_code,current_code,next_code) in self.sandwich_iter(gcode_in):    
            if(self.SF_handle_second_squirt_line):
                self.SF_handle_second_squirt_line = False
                continue

            if(self.seeking_squirt):
                #Check for more toolchanges whilst seeking the next squirt
                self.check_for_significant_toolchange(current_code)
                if(self.check_for_squirt(current_code+next_code)):
                    self.squirt_replace()
                    continue
            elif(self.seeking_first_layer):
                self.check_for_significant_toolchange(current_code)
                if(self.check_for_layer(current_code)):
                    self.seeking_first_layer = False
            else:
                if(self.check_for_snort(current_code+next_code)):
                    self.flush_buffer = True
                elif(self.check_for_significant_toolchange(current_code)):
                    if(self.seeking_first_toolchange):
                        match_prev = re.match(self.prime, previous_code)
                        match_next = re.match(self.prime, next_code)
                        if((match_prev is not None) or (match_next is not None)):
                            #If toolchanges are in the prime ignore
                            self.current_tool = self.last_tool
                            self.last_tool = -1
                        else:
                            #if this is the first significant toolchange do an extra squirt
                            self.seeking_first_toolchange = False
                            #little bit hacky to get first significant toolchange before output
                            #of squirt_tool()
                            self.buffer.append(current_code)
                            self.squirt_tool(self.current_tool, squirt_initial_inactive_tool=True)
                            #this is so duplicate current_codes aren't outputted
                            self.buffering = False
                    else:
                        self.seeking_squirt = True
                    self.snort_replace()

            if(self.flush_buffer):
                for line in self.buffer:
                    yield line
                self.buffer = []
                self.flush_buffer = False
            if(self.buffering):
                self.buffer.append(current_code)
            else:
                self.buffering = True

        #Squirt retracted tool at the end of the print
        self.squirt_tool(self.get_other_tool(self.current_tool))

        for line in self.buffer:
            yield line


    def check_if_in_prime(self, previous_code, next_code):
        """
            Checks if the current position is inside the prime block
            that is inserted by a related processor

            @param previous_code: string
            @param next_code: string
            @return: boolean: True if it is in the prime block
        """
        match_prev = re.match(self.prime, previous_code)
        match_next = re.match(self.prime, next_code)
        if((match_prev is not None) or (match_next is not None)):
            #If toolchanges are in the prime ignore
            self.current_tool = self.last_tool
            self.last_tool = -1
            return True
        else:
            return False


    def check_for_layer(self,string):
        match = re.match(self.layer_start, string)
        return match is not None


    def check_for_snort(self,string):
        """
        Check to see if input string is a snort
        if so it saves the snort values and returns
        
        @param string: string to be matched with the regex
        @return boolean: True if it is a snort
        """
        match = re.match(self.snort, string)
        if match is not None:
            extruder_position = match.group(1)
            if(extruder_position == None):
                extruder_position = match.group(2)
            self.last_snort['index'] = 0
            self.last_snort['tool'] = self.current_tool
            self.last_snort['extruder_position'] = float(extruder_position)
            #Check if this is a SF snort
            match = re.match(self.SF_feedrate, string)
            if match is not None:
                self.SF_flag = True
            return True
        else:
            return False


    def check_for_significant_toolchange(self,string):
        """
        Checks for significant toolchange(i.e. from tool 0 -> 1)
        Updates the current tool accordingly

        @param string: string to be matched to toolchange regex
        @return boolean: True if a significant toolchange is found
        """
        match = re.match(self.toolchange, string)
        if match is not None:
            if(self.current_tool == -1):
                self.current_tool = int(match.group(1))
                return False
            elif(self.current_tool != int(match.group(1))):
                self.last_tool = self.current_tool
                self.current_tool = int(match.group(1))
                return True
            else:
                return False
        else:
            return False


    def check_for_squirt(self, string):
        """
        Check if input string contains a squirt

        @param string: string to be matched to squirt regex
        @return boolean: True if squirt was found
        """
        match = re.match(self.squirt, string)
        if match is not None:
            extruder_position = match.group(1)
            if(extruder_position == None):
                extruder_position = match.group(2)
            self.squirt_extruder_pos = float(extruder_position)
            match = re.match(self.SF_feedrate, string)
            if match is not None:
                self.SF_handle_second_squirt_line = True
            self.seeking_squirt = False
            return True
        else:
            return False


    def get_other_tool(self, tool):
        inactive_tool = {0:1, 1:0}
        return inactive_tool.get(tool, -1)


    def squirt_tool(self, tool, squirt_initial_inactive_tool=False):
        """
            Inserts squirt command for given tool
            @param tool: integer, tool to squirt
            @param squirt_initial_inactve_tool: boolean, if this is the squirt of the initial
                significant toolchange
        """
        if not squirt_initial_inactive_tool:
            self.buffer.append("M135 T%i\n"%(tool))
            self.buffer.append("G92 %s0\n"%(self.TOOLHEADS[tool]))
        self.buffer.append("G1 F%f %s%f\n"%(self.squirt_feedrate, self.TOOLHEADS[tool],
            self.retract_distance_mm))
        self.buffer.append("G92 %s0\n"%(self.TOOLHEADS[tool]))
        

    def squirt_replace(self):
        new_extruder_position = self.squirt_extruder_pos-self.squirt_reduction_mm

        squirt_line = "G1 F%f %s%f\n"%(self.squirt_feedrate,
            self.TOOLHEADS[self.current_tool], new_extruder_position)
        self.buffer.append(squirt_line)
        #This G92 is to help reduce the blobbing that occurs on tool startup by reducing
        #the amount of plastic put out on squirt
        set_extruder_pos_line = "G92 %s%f\n"%(self.TOOLHEADS[self.current_tool],
            self.squirt_extruder_pos)
        self.buffer.append(set_extruder_pos_line)


    def snort_replace(self):
        """
        Replaces a past snort
        """
        if(self.last_snort['index'] != None):
            snort_index = self.last_snort['index']
            snort_extruder_position = self.last_snort['extruder_position']
            new_extruder_position = snort_extruder_position-self.retract_distance_mm

            snort_line = "G1 F%f %s%f\n"%(self.snort_feedrate,
                self.TOOLHEADS[self.last_tool], new_extruder_position)
            self.buffer[snort_index] = snort_line
            #if SF replace second line of the snort with a blank line
            if(self.SF_flag):
                self.buffer[snort_index+1] = '\n'

            #Reset Last Snort
            self.last_snort['index'] = None
            self.last_snort['tool'] = None
            self.last_snort['extruder_position'] = None


    def profile_supports_processor(self):
        if(self.retract_distance_mm == 'NULL'):
            return False
        else:
            return True

