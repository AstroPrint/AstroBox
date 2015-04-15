from __future__ import absolute_import

import makerbot_driver


class ProcessorFactory(object):

    def __init__(self):
        pass

    def list_processors(self):
        pros = makerbot_driver.GcodeProcessors.all
        if 'errors' in pros:
            pros.remove('errors')
        return pros

    def create_processor_from_name(self, name, profile = None):
        try:
            processor = getattr(makerbot_driver.GcodeProcessors, name)()
            processor.profile = profile
            return processor
        except AttributeError:
            raise makerbot_driver.GcodeProcessors.ProcessorNotFoundError

    def process_list_with_commas(self, string):
        string = string.replace(' ', '')
        strings = string.split(',')
        for s in strings:
            if s == '':
                strings.remove(s)
        return strings

    def get_processors(self, processors, profile = None):
        if isinstance(processors, str):
            processors = self.process_list_with_commas(processors)
        for processor in processors:
            yield self.create_processor_from_name(processor, profile)

    def create_cascading_generator(self, processors, gcode, gcode_info, profile = None):
        """
            This creates a single generator which yields the final output from a chain
            of gcode processors

            @param processors: list of processors to chain together (order is important)
            @param gcode: iterable of the gcode to process
            @param gcode_info: dict that holds metadata about the gcode used by the processors
            @param profile: profile object

            @return: generator object
        """

        processors = list(self.get_processors(processors, profile))
        first_processor = True
        process_generator = None
        for processor in processors:
            if(first_processor):
                process_generator = processor.process_gcode(gcode, gcode_info)
                first_processor = False
            else:
                process_generator = processor.process_gcode(process_generator, gcode_info)
        return process_generator

