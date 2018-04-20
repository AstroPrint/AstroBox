var AdditionalTasksView = Backbone.View.extend({
  el: '#additional-tasks-view',
  additionalTasksListView: null,
  upload: null,
  initialize: function()
  {
    this.additionalTasksListView = new AdditionalTasksListView();
    this.uploader = new TaskUploader({
      el: this.$('input.file-upload'),
      progressBar: this.$('.upload-progress'),
      buttonContainer: this.$('.upload-buttons'),
      installedCallback: _.bind(this.onTaskInstalled,this)
    });
  },
  onTaskInstalled: function()
  {
    noty({type: "success", text: "Task Installed", timeout: 3000});
    this.additionalTasksListView.refreshList();
  }
});

// Custom actions menu
var AdditionalTasksListView = Backbone.View.extend({
  el: '#task-list',
  additionalTask_views: [],
  additionalTaskCollection: null,
  initialize: function()
  {
    this.additionalTaskCollection = new AdditionalTaskCollection();
    this.refreshList();
  },
  refreshList: function()
  {
    this.additionalTaskCollection.reset();
    $.getJSON(API_BASEURL + 'additional-tasks', null, _.bind(function(data) {
      if (data.utilities && data.utilities.length) {
        for (var i = 0; i < data.utilities.length; i++) {
          var adTask = data.utilities[i];
          if (adTask.visibility) {
            this.additionalTaskCollection.add(new AdditionalTask(adTask))
          }
        }
        this.render();
      }
    }, this))
    .fail(function() {
      noty({text: "There was an error getting additional tasks.", timeout: 3000});
    })
  },
  render: function()
  {
    this.$el.empty();
    // Render each box
    this.additionalTaskCollection.each(function (additionalTaskApp) {
      var row = new AdditionalTaskRowView({ additionalTaskApp: additionalTaskApp});
      this.$el.append(row.render().el);
      this.additionalTask_views[additionalTaskApp.get('id')] = row;
    }, this);
  }
});

var AdditionalTaskRowView = Backbone.View.extend({
  className: 'task-row',
  tagName: 'li',
  additionalTaskApp: null,
  template: _.template($("#task-row-template").html()),
  initialize: function (params)
  {
    this.additionalTaskApp = params.additionalTaskApp;
    this.$el.attr('id', this.additionalTaskApp.get('id'));
  },
  render: function ()
  {
    this.$el.empty();
    this.$el.html(this.template({ view: this, additionalTaskApp: this.additionalTaskApp.toJSON() }));
    return this;
  }
});

var TaskUploader = FileUploadBase.extend({
  progressBar: null,
  buttonContainer: null,
  installedCallback: null,
  initialize: function(options)
  {
    FileUploadBase.prototype.initialize.call(this, options);

    this.progressBar = options.progressBar;
    this.buttonContainer = options.buttonContainer;
    this.$el.attr('accept', '.zip');
    this.acceptFileTypes = /(\.|\/)(zip)$/i;
    this.uploadUrl = API_BASEURL + 'additional-tasks';
    this.installedCallback = options.installedCallback;
  },
  started: function(data)
  {
    if (data.files && data.files.length > 0) {
      this.buttonContainer.hide();
      this.progressBar.show();
      FileUploadBase.prototype.started.call(this, data);
    }
  },
  failed: function(error)
  {
    var message = null;
    switch(error) {
      case 'invalid_file':
        message = 'The file is not a valid task';
      break;

      case 'invalid_task_file':
        message = 'The task file has errors';
      break;

      case 'error_checking_file':
        message = 'There was an error checking the task file';
      break;

      case 'invalid_tasks_definition':
        message = 'The task definition file is not valid';
      break;

      case 'incompatible_task':
        message = 'The API version used by the task is not compatible.';

      case 'already_installed':
        message = "The Task is already installed. Please remove old version first.";
      break;
    }

    this.onError(message);
  },
  success: function(data)
  {
    if (data.result.tmp_file) {
      $.ajax({
        url: API_BASEURL + 'additional-tasks/install',
        method: 'POST',
        type: 'json',
        contentType: 'application/json',
        data: JSON.stringify({
          file: data.result.tmp_file
        })
      })
        .done(_.bind(function(){
          this.onPrintFileUploaded();
          this.installedCallback(data.result);
        }, this))
        .fail(_.bind(function(){
          this.onError('Unable to install task');
        }, this))
    } else {
      this.onError('Unable to install task');
    }
  },
  progress: function(progress, message)
  {
    var intPercent = Math.round(progress);

    this.progressBar.find('.meter').css('width', intPercent+'%');
    if (!message) {
      message = "Uploading ("+intPercent+"%)";
    }
    this.progressBar.find('.progress-message span').text(message);
  },
  onError: function(error)
  {
    noty({text: error ? error : 'There was an error uploading your file', timeout: 3000});
    this.resetUploadArea();
    console.error(error);
  },
  onPrintFileUploaded: function()
  {
    this.resetUploadArea();
  },
  resetUploadArea: function()
  {
    this.progressBar.hide();
    this.buttonContainer.show();
    this.progress(0);
  }
});
