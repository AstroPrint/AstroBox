from __future__ import absolute_import

import json
import makerbot_driver

"""
A machine profile object that holds all values for a specific profile.
"""

import json
import os
import re
import logging

GcodeRecipes =  {
  "PLA" : {
    "print_start_sequence" : {
      "heat_platform" : "no_heat"
      },
    "print_end_sequence" : {
      "cool_platform" : "no_cool"
      },
    "variables" : {
      "TOOL_0_TEMP" : 230,
      "TOOL_1_TEMP" : 230
      }
  },
  "ABS" : {
    "print_start_sequence" : {
      "heat_platform" : "heat_platform"
      },
    "print_end_sequence" : {
      "cool_platform" : "cool_platform"
      },
    "variables" : {
      "TOOL_0_TEMP" : 230,
      "TOOL_1_TEMP" : 230,
      "PLATFORM_TEMP" : 110
      }
    },
  "dualstrusion": {
    "print_start_sequence" : {
      "heat_tools" : "dualstrusion"
      },
    "print_end_sequence" : {
      "cool_tools" : "dualstrusion"
      },
    "variables" : {}
    }
}

class GcodeAssembler(object):
    """
    An assembler that builds start and end gcodes.
    In makerbot_driver/profiles/recipes.json there are
    several recipes defined, each with a set of routines.

    """

    def __init__(self, machine_profile, profiledir=None):
        self.machine_profile = machine_profile
        self.start_order = [
            'begin_print',
            'homing',
            'start_position',
            'heat_platform',
            'heat_tools',
            'end_start_sequence',
        ]
        self.end_order = [
            'end_position',
            'cool_platform',
            'cool_tools',
            'end_print',
        ]
        self.recipes = GcodeRecipes

    def assemble_recipe(self,
                        material='PLA',
                        tool_0=True,
                        tool_1=False,
                        begin_print='replicator_begin',
                        homing='replicator_homing',
                        start_position='replicator_start_position',
                        end_start_sequence='replicator_end_start_sequence',
                        end_position='replicator_end_position',
                        end_print='replicator_end',
                        heat_platform_override=False,
                        no_heat_platform_override=False,
                        ):
        """
        The recipe assembler.  Has several built in
        defaults a user could use to create a generic
        sequence recipe.  If both tool_0 and tool_1 are
        set to true, will assume it should output in
        dualstrusion mode.

        @return dict start_recipe: The recipe used to
          build the print start sequence.
        @return dict end_recipe: The recipe used to
          build the print end sequence.
        @return dict variables: The default variables
          used by the gcode parser.
        """
        start_recipe = {}
        end_recipe = {}
        variables = {}
        #Check for dualstrusion
        if tool_0 and tool_1:
            dual_start_recipe, dual_end_recipe, dual_variables = self.get_recipes_and_variables('dualstrusion')
            start_recipe.update(dual_start_recipe)
            end_recipe.update(dual_end_recipe)
            variables.update(dual_variables)
        elif tool_0:
            #Update start routine
            start_recipe.update({'heat_tools': 'heat_0'})
            #Update end routine
            end_recipe.update({'cool_tools': 'cool_0'})
        elif tool_1:
            #Update start routine
            start_recipe.update({'heat_tools': 'heat_1'})
            #Update end routine
            end_recipe.update({'cool_tools': 'cool_1'})
        #Add material values to the return template values
        mat_start_recipe, mat_end_recipe, mat_variables = self.get_recipes_and_variables(material)
        start_recipe.update(mat_start_recipe)
        end_recipe.update(mat_end_recipe)
        variables.update(mat_variables)
        start_recipe.update({
            'begin_print': begin_print,
            'homing': homing,
            'start_position': start_position,
            'end_start_sequence': end_start_sequence,
        })
        end_recipe.update({
            'end_position': end_position,
            'end_print': end_print
        })
        if heat_platform_override:
            start_recipe.update({'heat_platform': 'heat_platform'})
            end_recipe.update({'cool_platform': 'cool_platform'})
        if no_heat_platform_override:
            start_recipe.update({'heat_platform': None})
            end_recipe.update({'cool_platform': None})
        return start_recipe, end_recipe, variables

    def assemble_start_sequence(self, recipe):
        """
        Given a start recipe, assembles the correct sequence

        @param recipe: The recipe used to create the sequence
        @return list gcodes: Sequence of gcodes derived from the recipe
        """
        order = self.start_order
        template_name = 'print_start_sequence'
        gcodes = self.assemble_sequence_from_recipe(
            recipe, template_name, order)
        return gcodes

    def assemble_end_sequence(self, recipe):
        """
        Given an end recipe, assembles the correct sequence

        @param recipe: The recipe used to create the sequence
        @return list gcodes: Sequence of gcodes derived from the recipe
        """
        order = self.end_order
        template_name = 'print_end_sequence'
        gcodes = self.assemble_sequence_from_recipe(
            recipe, template_name, order)
        return gcodes

    def assemble_sequence_from_recipe(self, recipe, template_name, order):
        """
        Given a recipe, template_name and ordering creates the correct
        sequence.

        @param recipe: The recipe used to create the sequence
        @param template_name: The name of the template we want to use (start/end)
        @param order: The correct ordering of routines

        @return list gcodes: Sequence of gcodes derived from the recipe.
        """
        gcodes = []
        template = self.machine_profile.values[template_name]
        for routine in order:
            if recipe[routine] is not None:
                gcodes.extend(template[routine][recipe[routine]])
        return gcodes

    def get_recipes_and_variables(self, key):
        """
        Given a recipe (i.e. PLA, ABS, dualstrusion), gets its start
        routines, end routines and variables.

        @param key: Name of the recipe we want to access
        @return dict start_routines: The start routines associated with this key
        @return dict end_routines: The end routines associated with this key
        @return dict variables: The variables associated with this key
        """

        if not key in self.recipes:
            raise makerbot_driver.RecipeNotFoundError
        values = self.recipes[key]
        start_routines = values['print_start_sequence']
        end_routines = values['print_end_sequence']
        variables = values['variables']
        return start_routines, end_routines, variables

