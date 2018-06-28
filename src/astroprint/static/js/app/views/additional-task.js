var AdditionalTaskView = Backbone.View.extend({
  el: '#additional-task-view',
  additionalTaskContainerView: null,
  events: {
    'hide': 'onHide'
  },
  initialize: function(additionalTaskSequenceID)
  {
    this.additionalTaskContainerView = new AdditionalTaskContainerView(additionalTaskSequenceID);
  },
  onHide: function()
  {
    var taskAppView = this.additionalTaskContainerView.additionalTaskApp_view;
    if (taskAppView) {
      taskAppView.cleanAndUndelegate()
    }
  }
});

var AdditionalTaskContainerView = Backbone.View.extend({
  el: '#additional-task-app-container',
  additionalTaskApp: null,
  additionalTaskApp_view: null,
  initialize: function(additionalTaskSequenceID)
  {
    if (app.router.additionalTasksView) {
      this.additionalTaskApp = app.router.additionalTasksView.additionalTasksListView.additionalTaskCollection.findWhere({ id: additionalTaskSequenceID });
      this.render();
    } else {
      this.getSequence(additionalTaskSequenceID).then(
        _.bind(function(success) {
          this.render();
        }, this),
        _.bind(function(error) {
          console.error('error', error);
          this.render();
        }, this)
      );
    }
  },
  getSequence: function(additionalTaskSequenceID)
  {
    return $.getJSON(API_BASEURL + 'additional-tasks', null, _.bind(function(data) {
      if (data) {
        var task = _.find(data, function(task) { return task.id == additionalTaskSequenceID && task.visibility });
        if (task) {
          this.additionalTaskApp = new AdditionalTask(task);
        }
      }
    }, this))
    .fail(function() {
      noty({text: "There was an error getting additional task.", timeout: 3000});
    })
  },

  render: function()
  {
    var actionEl = this.$el.find('.additional-tasks-app');
    var noActionEl = this.$el.find('#additional-task');

    actionEl.empty();
    noActionEl.hide();

    if (this.additionalTaskApp) {
      var row = new AdditionalTaskAppView({ additionalTaskApp: this.additionalTaskApp});
      actionEl.append(row.render().el);
      this.additionalTaskApp_view = row;
    } else {
      noActionEl.show();
      setTimeout(function() {
        app.router.navigate("#additional-tasks", {trigger: true});
      }, 2500);
    }
  }
});

var AdditionalTaskAppView = Backbone.View.extend({
  className: 'additional-task-row',
  additionalTaskApp: null,
  currentIndexStep: 1,
  currentStep: null,
  customTempView: null,
  controlView: null,
  modal: null,
  isModal: false,
  events: {
    "click .close": "closeClicked",
    "click .next": "nextClicked",
    "click .back": "backClicked",
    "click .action": "actionClicked",
    "click .repeat": "repeatClicked"
  },
  template: null,
  initialize: function (params)
  {
    this.additionalTaskApp = params.additionalTaskApp;
    this.currentStep = this.additionalTaskApp.get('steps')[this.currentIndexStep-1]
    this.$el.attr('id', this.additionalTaskApp.get('id'));
  },
  render: function ()
  {
    if (!this.template) {
      this.template = _.template($("#additional-task-app-template").html());
    }

    this.$el.empty();
    var params = {};
    if (!this.isModal) {
      params = {currentStep: this.currentStep, currentIndexStep: this.currentIndexStep, additionalTaskApp: this.additionalTaskApp.toJSON(), isModal: this.isModal }
    } else {
      params = { currentStep: this.modal, additionalTaskApp: this.additionalTaskApp.toJSON(), isModal: this.isModal }
    }

    this.$el.html(this.template(params));

    // Add Control view widget
    if (this.currentStep.type == "control_movement" ||  (this.isModal && this.modal.type == "control_movement")) {
      this.controlView = new ControlView({ignorePrintingStatus: true});
      this.$el.find('#control-container').append(this.controlView.render());
    }
    if (!this.isModal){
      this.currentStepManagement()
    } else {
      if (this.modal.on_enter_commands) {
        this.sendCommands('on_enter', this.modal.on_enter_commands);
      }
    }
    return this;
  },
  cleanAndUndelegate: function ()
  {
    if (this.customTempView) {
      this.customTempView.stopListening();
    }
  },
  closeClicked: function (e)
  {
    e.preventDefault();
    this.doClose();
  },

  doClose: function()
  {
    window.history.back();
  },

  currentStepManagement: function()
  {
    this.currentStep = this.additionalTaskApp.get('steps')[this.currentIndexStep-1];
    // If Show temp view
    if (this.currentStep.type == "set_temperature") {
      var loadingBtn = this.$('button.next').closest('.loading-button');
      loadingBtn.addClass('inactive');
      setTimeout( _.bind(function() {
        this.customTempView = new CustomTempView();
      },this), 300);
    }

    if (this.currentStep.on_enter_commands) {
      this.sendCommands('on_enter', this.currentStep.on_enter_commands);
    }
  },

  nextClicked: function (e)
  {
    e.preventDefault();
    this.checkStepType("next");
  },

  backClicked: function (e)
  {
    e.preventDefault();
    if (!this.isModal) {
      this.checkStepType("back");
    } else {
      this.isModal = false;
      this.modal = null;
      this.render();
    }
  },

  checkStepType: function(direction)
  {
    var loadingBtn = this.$('button.next').closest('.loading-button');
    if (this.currentStep.type == "set_extruder") {
      // Change active extruder
      this._sendChangeToolCommand(this.$('#extruder-count').val())
        .done(_.bind(function () {
          loadingBtn.removeClass('loading');
          this.checkForCommandsAndMove(direction);
        }, this))
        .fail(function () {
          loadingBtn.addClass('failed');
          noty({ text: "There was an error sending a command.", timeout: 3000 });
          setTimeout(function () {
            loadingBtn.removeClass('failed');
          }, 3000);
        });
    } else if (this.currentStep.type == "set_temperature") {
      this.customTempView.stopListening();
      this.checkForCommandsAndMove(direction);
    } else {
      this.checkForCommandsAndMove(direction);
    }
  },

  checkForCommandsAndMove: function(direction)
  {
    var loadingBtn = this.$('button.next').closest('.loading-button');
    loadingBtn.addClass("loading");
    if ( direction == "next" && this.currentStep.next_button.commands || direction == "back" && this.currentStep.back_button.commands) {
      this.sendCommands(direction)
        .done(_.bind(function() {
          loadingBtn.removeClass('loading');
          if (direction == "next") { this.checkNextStep()} else {this.goBackStep()}
        },this))
        .fail(function() {
          loadingBtn.addClass('failed');
          noty({ text: "There was an error sending a command.", timeout: 3000 });
          setTimeout(function () {
            loadingBtn.removeClass('failed');
          }, 3000);
        });
    } else {
      if (direction == "next") { this.checkNextStep()} else {this.goBackStep()}
    }
  },

  actionClicked: function (e)
  {
    e.preventDefault();
    this.doAction();
  },

  doAction: function()
  {
    var actions = this.isModal ? this.modal.actions.commands : this.currentStep.actions.commands;
    if (actions && Array.isArray(actions)) {
      // Multiple actions
      if (actions[0] !== null && typeof actions[0] === 'object') {
        new MultipleActionsDialog({actions: actions, title: this.currentStep.actions.name.en, stepView: this }).open();
      // Single action
      } else {
        this.sendCommands("action");
      }
    }
  },

  linkTo: function(ID)
  {
    if (this.currentStep.type == "set_temperature") {
      this.customTempView.stopListening();
    }
    var stepToGoData = this._getStepByID(ID);

    if (stepToGoData) {
      this.isModal = false;
      this.currentIndexStep = stepToGoData.index+1;
      this.currentStep = stepToGoData.step;
    } else {
      var modalToGoData = this._getModalByID(ID);
      if (modalToGoData) {
        this.modal = modalToGoData;
        this.isModal = true;
      }
    }
    this.render()
  },

  repeatClicked: function (e)
  {
    e.preventDefault();
    this.doRepeat();
  },

  doRepeat: function()
  {
    this.currentIndexStep = 1;
    this.currentStep = this.additionalTaskApp.get('steps')[this.currentIndexStep-1]
    this.render();
  },

  goBackStep: function()
  {
    this.currentIndexStep--;
    this.currentStep = this.additionalTaskApp.get('steps')[this.currentIndexStep-1]
    this.render();
  },

  checkNextStep: function()
  {
    // If no Last step
    if (this.currentIndexStep < this.additionalTaskApp.get('steps').length) {
      this.currentIndexStep++;
      this.currentStep = this.additionalTaskApp.get('steps')[this.currentIndexStep-1]
      this.render();
    // If Last step
    } else {
      this.doClose();
    }
  },


  sendCommands: function (type, arrayCommands, linkID, commandsIndex, promise )
  {

    if (!commandsIndex) { var commandsIndex = 0;}

    if (!promise) { var promise = $.Deferred();}

    if (!arrayCommands) {
      arrayCommands = [];
      if (!this.isModal) {
        if (type == "action") {
          arrayCommands = this.currentStep.actions.commands;
        } else if (type == "next") {
          arrayCommands = this.currentStep.next_button.commands;
        } else if (type == "back") {
          arrayCommands = this.currentStep.back_button.commands;
        }
      } else {
        if (type == "action") {
          arrayCommands = this.modal.actions.commands;
        } else if (type == "back") {
          arrayCommands = this.modal.back_button.commands;
        }
      }

    }

    var currentCommand = arrayCommands[commandsIndex];

    // Check if it's a step-link ID
    if (type == "action" && currentCommand.startsWith("@")) {
      linkID = currentCommand.replace('@', '');
      currentCommand = arrayCommands[++commandsIndex];

      if (!currentCommand) {
        this.linkTo(linkID);
        promise.resolve();
        return promise;
      }
    }
    $.ajax({
      url: API_BASEURL + 'printer/comm/send',
      method: 'POST',
      data: {
        command: currentCommand
      }
    })
      .success(_.bind(function () {
        if (arrayCommands[commandsIndex + 1]) {
          this.sendCommands(type, arrayCommands, linkID, ++commandsIndex, promise);
        } else {
          promise.resolve();
          if (linkID) {
            this.linkTo(linkID);
          }
        }
      }, this))

      .fail(_.bind(function () {
        promise.reject()
      }, this))

    return promise;
  },

  _sendChangeToolCommand: function(tool)
  {
    var data = {
      command: "select",
      tool: 'tool'+tool
    }

    return $.ajax({
      url: API_BASEURL + "printer/tool",
      type: "POST",
      dataType: "json",
      contentType: "application/json; charset=UTF-8",
      data: JSON.stringify(data)
    });
  },

  _getStepByID: function(ID)
  {
    var steps = this.additionalTaskApp.get('steps');
    var result = null;

    for (i = 0; i < steps.length; i++) {
      if (steps[i].id == ID) {
        result = {"step" : steps[i],"index": i};
      }
    }
    return result;
  },

  _getModalByID: function(ID)
  {
    var modal = this.additionalTaskApp.get('modals');
    var result = null;

    for (i = 0; i < modal.length; i++) {
      if (modal[i].id == ID) {
        result = modal[i];
      }
    }
    return result;
  }
});

var CustomTempView = Backbone.View.extend({
  className: 'control-temps small-12 columns',
  el: '#custom-temp-control-template',
  semiCircleTempView: null,
  currentExtruder: 0,
  socketTemps: null,
  initialize: function()
  {
    new SemiCircleProgress();
    var profile = app.printerProfile.toJSON();
    if (app.socketData.get('tool') >= 0) {
      this.currentExtruder = app.socketData.get('tool');
    }
    this.renderCircleTemps();
    this.listenTo(app.socketData, 'change:temps', this.onTempsChanged);
    this.listenTo(app.socketData, 'change:paused', this.onPausedChanged);
    this.listenTo(app.socketData, 'change:tool', this.onToolChanged);
  },
  renderCircleTemps: function() {
    if (app.socketData.attributes.temps != this.socketTemps) {
      this.socketTemps = app.socketData.attributes.temps;
    }
    var temps = null;

    this.$el.find('#slider-nav').empty();
    this.$el.find('#slider').empty();
    this.$el.find('.bed').empty();

    this.semiCircleTempView = new TempSemiCircleView({'tool': this.currentExtruder, enableOff: false, hideBed: true, preHeat: true});

    this.$el.find('#slider').append(this.semiCircleTempView.render().el);

    if (this.socketTemps.extruders) {
      temps = {
        current: this.socketTemps.extruders[this.currentExtruder].current,
        target: this.socketTemps.extruders[this.currentExtruder].target
      };
    } else {
      temps = {current: null, target: null};
    }


    this.semiCircleTempView.setTemps(temps.current, temps.target);

    // Draw circle
    this.$el.find("#"+this.semiCircleTempView.el.id+" .progress-temp-circle").circleProgress({
      arcCoef: 0.55,
      size: 180,
      thickness: 20,
      fill: { gradient: ['#60D2E5', '#E8A13A', '#F02E19'] }
    });
    if (this.socketTemps.extruders) {
      this.updateTemps(this.socketTemps);
    }
  },

  onTempsChanged: function(socketTempData)
  {
    var temp_values = socketTempData.get('temps');
    this.updateTemps(temp_values);
  },

  updateTemps: function(temp_values)
  {
    var temps = { 'current': temp_values.extruders[this.currentExtruder].current, 'target': temp_values.extruders[this.currentExtruder].target };

    (this.semiCircleTempView).updateValues(temps);

    if (this.semiCircleTempView.type == 'tool') {

      var tempValue = '- -';
      if (this.semiCircleTempView.actual != null) {
        tempValue = Math.round(this.semiCircleTempView.actual) + 'º';
      }
      this.$el.find("#tool"+this.currentExtruder).find('.all-temps').text(tempValue);
    }

    this.$("#"+this.semiCircleTempView.el.id+" .progress-temp-circle").circleProgress({
      arcCoef: 0.55,
      size: 180,
      thickness: 20,
      fill: { gradient: ['#60D2E5', '#E8A13A', '#F02E19'] }
    });

    if (temp_values.extruders[this.currentExtruder].current >= temp_values.extruders[this.currentExtruder].target ) {
      var loadingBtn = $('button.next').closest('.loading-button');
      loadingBtn.removeClass('inactive');
    }

  }
});

//~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
// Multiple actions Dialog
//~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

var MultipleActionsDialog = Backbone.View.extend({
  el: '#multiple-actions-dlg',
  actions: [],
  stepView: null,
  events: {
    "click .action": "actionClicked",
    "click button.cancel": "doCancel",
    'closed.fndtn.reveal': 'onClosed',
    'opened.fndtn.reveal': 'onOpened'
  },
  initialize: function(opts)
  {
    this.actions = opts.actions;
    this.title = opts.title;
    this.stepView = opts.stepView
  },
  render: function()
  {
    this.$('.title-dlg').text(this.title);
    var actionsContainer = this.$('.actions-container');
    actionsContainer.empty();
    for (var i = 0; i <  this.actions.length; i++) {
      var ac =  this.actions[i];
      actionsContainer.append("<div class='action bold' data-id='"+ i +"'>"+ ac.name.en +"</div>");
    }
  },
  open: function()
  {
    this.render();
    this.$el.foundation('reveal', 'open');
  },

  actionClicked: function( e )
  {
    e.preventDefault();
    var action = $(e.currentTarget);

    this.doAction(action.data("id"));
  },

  doAction: function(actionID) {
    this.stepView.sendCommands("action", this.actions[actionID].commands);
    for (var i = 0; i < this.actions[actionID].commands.length; i++) {
      var element = this.actions[actionID].commands[i];
      if (element.startsWith("@")) {
        this.doCancel();
      }
    }
  },

  doCancel: function()
  {
    this.$el.foundation('reveal', 'close');
  },
  onClosed: function()
  {
    this.undelegateEvents();
  }
});
