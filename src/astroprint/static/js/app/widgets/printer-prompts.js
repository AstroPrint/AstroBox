/*
 *  (c) AstroPrint Product Team. 3DaGoGo, Inc. (product@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

// global app

var PrinterPromptController = Backbone.View.extend({
  el: '#printer-prompt-modal',
  eventManager: null,
  template: null,
  events: {
    'click .prompt-choice': "onChoiceClicked",
    'click .close': 'onCloseClicked'
  },
  initialize: function(options)
  {
    this.eventManager = options.eventManager
    this.eventManager.on('astrobox:printer_prompt', this.onEvent, this);
  },
  render: function(message, choices)
  {
    if (!this.template) {
      this.template = _.template($('#printer-prompt-modal-template').html())
    }

    this.$el.html(this.template({
      message: message,
      choices: choices
    }));
  },
  onEvent: function(payload)
  {
    var type = payload.type

    switch(type) {
      case 'show':
        var prompt = payload.prompt

        this.render(prompt.message, prompt.choices)
        this.$el.foundation('reveal', 'open', {
          close_on_background_click: false,
          close_on_esc: false
        })
        break;

      case 'close':
        this.$el.foundation('reveal', 'close')
        break;
    }
  },
  onChoiceClicked: function(e)
  {
    e.preventDefault()

    var $btn = $(e.target)
    var choiceIdx = $btn.data('choice')

    console.log('choice ' + choiceIdx + ' clicked')
    this.$el.foundation('reveal', 'close')
  },
  onCloseClicked: function(e)
  {
    e.preventDefault()
    this.$el.foundation('reveal', 'close')
  }
})
