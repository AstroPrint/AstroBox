var CustomActionView = Backbone.View.extend({
  el: '#custom-action-view',
  customActionContainerView: null,
  initialize: function(customActionSequenceID)
  {
    this.customActionContainerView = new CustomActionContainerView(customActionSequenceID);
  }
});

var CustomActionContainerView = Backbone.View.extend({
  el: '#custom-action-app-container',
  customActionApp: null,
  customActionApp_views: [],
  initialize: function(customActionSequenceID)
  {
    if (app.router.customActionsView) {
      this.customActionApp = app.router.customActionsView.customActionsListView.customizedActionCollection.findWhere({ id: customActionSequenceID });
      this.render();
    } else {
      this.getSequence(customActionSequenceID).then(
        success => {
          this.render();
        },
        error => {
          console.error('error', error);
          this.render();
        }
      );
    }
  },

  getSequence(customActionSequenceID)
  {
    return $.getJSON(API_BASEURL + 'custom-actions', null, _.bind(function(data) {
      if (data.utilities && data.utilities.length) {
        for (var i = 0; i < data.utilities.length; i++) {
          let ca = data.utilities[i];
          if (ca.id == customActionSequenceID && ca.visibility) {
            this.customActionApp = new CustomizedAction(ca);
          }
        }
      }
    }, this))
    .fail(function() {
      noty({text: "There was an error getting customized command.", timeout: 3000});
    })
  },

  render: function()
  {
    var actionEl = this.$el.find('.custom-action-app');
    var noActionEl = this.$el.find('#no-found-action');

    actionEl.empty();
    noActionEl.hide();

    if (this.customActionApp) {
      var row = new CustomActionAppView({ customActionApp: this.customActionApp});
      actionEl.append(row.render().el);
      this.customActionApp_views[this.customActionApp.get('id')] = row;
    } else {
      noActionEl.show();
      setTimeout(() => {
        window.location.href = window.location.origin+"/#custom"
      }, 2500);
    }
  }
});

var CustomActionAppView = Backbone.View.extend({
  className: 'action-app-row',
  customActionApp: null,
  currentIndexStep: 1,
  currentStep: null,
  events: {
    "click .close": "closeClicked",
    "click .next": "nextClicked",
    "click .repeat": "repeatClicked"
  },
  template: _.template($("#custom-action-app-template").html()),
  initialize: function (params)
  {
    this.customActionApp = params.customActionApp;
    this.currentStep = this.customActionApp.get('steps')[this.currentIndexStep-1]

    this.$el.attr('id', this.customActionApp.get('id'));
  },
  closeClicked: function (e)
  {
    e.preventDefault();
    this.doClose();
  },

  doClose()
  {
    let currentLocation = window.location
    currentLocation.href = currentLocation.origin+"/#custom"
  },
  nextClicked: function (e)
  {
    e.preventDefault();
    this.doNext();
  },
  doNext()
  {
    if (this.currentStep.commands.length) {
      var loadingBtn = this.$('button.next').closest('.loading-button');
      loadingBtn.addClass('loading');
      this.sendCommands(null, null)
        .done(() => {
          console.info('All the commands have been sent');
          loadingBtn.removeClass('loading');
          this.stepManagement();
        })
        .fail(() => {
          loadingBtn.addClass('failed');
          noty({ text: "There was an error sending a command.", timeout: 3000 });
          setTimeout(function () {
            loadingBtn.removeClass('failed');
          }, 3000);
        });
    } else {
      this.stepManagement();
    }
  },

  repeatClicked: function (e)
  {
    e.preventDefault();
    this.doRepeat();
  },

  doRepeat: function()
  {
    this.currentIndexStep = 1;
    this.currentStep = this.customActionApp.get('steps')[this.currentIndexStep-1]
    this.render();
  },

  stepManagement: function()
  {
    if (this.currentIndexStep < this.customActionApp.get('steps').length) {
      this.currentIndexStep++;
      this.currentStep = this.customActionApp.get('steps')[this.currentIndexStep-1]
      this.render();
    } else {
      this.doClose();
    }
  },

  sendCommands: function(commandsIndex, promise)
  {
    if (!commandsIndex) {
      var commandsIndex = 0;
    }
    if (!promise) {
      var promise = $.Deferred();
    }

     $.ajax({

      url: API_BASEURL + 'printer/comm/send',
      method: 'POST',
      data: {
        command: this.currentStep.commands[commandsIndex]
      }
    })
      .success(( () => {
        if (this.currentStep.commands[commandsIndex+1]) {
          setTimeout(() => {
            this.sendCommands(++commandsIndex, promise);
          }, 300);
        } else {
         promise.resolve();
        }

      }))

      .fail(_.bind(function () {
        promise.reject()
      }, this))

      return promise;
  },

  render: function ()
  {
    this.$el.empty();
    this.$el.html(this.template({currentStep: this.currentStep, currentIndexStep: this.currentIndexStep, customActionApp: this.customActionApp.toJSON() }));
    return this;
  },
});
