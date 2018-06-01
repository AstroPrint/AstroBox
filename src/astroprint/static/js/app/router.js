/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var AppRouter = Backbone.Router.extend({
  homeView: null,
  filesView: null,
  utilitiesView: null,
  settingsView: null,
  additionalTasksView: null,
  additionalTaskView: null,
  maintenanceMenu: null,
  printingView: null,
  terminalView: null,
  cameraView: null,
  suppliesView: null,
  helpView: null,
  routes: {
    "": "home",
    "files": "files",
    "file-info/:fileId": "fileInfo",
    "utilities": "utilities",
    "printing": "printing",
    "settings": "settings",
    "additional-tasks": "additionalTasks",
    "additional-tasks/:sequence_id": "additionalTask",
    "maintenance-menu": "maintenanceMenu",
    "settings/:page": "settings",
    "gcode-terminal": "terminal",
    "camera": "camera",
    "supplies": "supplies",
    "help": "help",
    "*notFound": "notFound"
  },
  turningOff: false,
  execute: function(callback, args)
  {
    if (callback) {
      is_paused = app.socketData.get('paused');
      is_printing = app.socketData.get('printing');

      if (is_printing || is_paused) {
        app.setPrinting();

        // Redirect to printing if printingView or utilitiesView are not the cb
        if (callback != this.printing && callback != this.utilities) {
          this.navigate('printing', {trigger: true, replace:true});
          return;
        }
      } else if (callback == this.printing) {
        this.navigate('', {trigger: true, replace:true});
        return;
      }

      callback.apply(this, args);
    }
  },
  home: function()
  {
    if (!this.homeView) {
      this.homeView = new HomeView({forceSync: false});
    }

    this.selectView(this.homeView);
    app.selectQuickNav('dash');
  },
  files: function()
  {
    this.loadFilesView(false);
    this.selectView(this.filesView);
    app.selectQuickNav('files');
  },
  fileInfo: function(fileId)
  {
    var showDlg = _.bind(function(success) {
      if (success) {
        this.filesView.fileInfo(fileId);
      }
    }, this);

    if (this.filesView) {
      this.filesView.printFilesListView.refresh(true, showDlg);
    } else {
      this.filesView = new FilesView({
        forceSync: true,
        syncCompleted: showDlg
      });
    }

    this.navigate('files', {trigger: true, replace:true});
  },
  utilities: function()
  {
    if (!this.utilitiesView) {
      this.utilitiesView = new UtilitiesView();
    }

    this.selectView(this.utilitiesView);
    app.selectQuickNav('utilities');
  },
  printing: function()
  {
    if (!this.printingView) {
      this.printingView = new PrintingView();
    }

    this.selectView(this.printingView);
  },
  settings: function(page)
  {
    if (!this.settingsView) {
      this.settingsView = new SettingsView();
    }

    this.selectView(this.settingsView);
    this.settingsView.menu.changeActive(page);
    app.selectQuickNav('settings');
  },
  maintenanceMenu: function()
  {
    if (!this.MaintenanceMenuView) {
      this.MaintenanceMenuView = new MaintenanceMenuView();
    }

    this.selectView(this.MaintenanceMenuView);

  },
  additionalTasks: function()
  {
    if (!this.additionalTasksView) {
      this.additionalTasksView = new AdditionalTasksView();
    }

    this.selectView(this.additionalTasksView);

  },
  additionalTask: function(sequence_id)
  {
    this.additionalTaskView = new AdditionalTaskView(sequence_id);
    this.selectView(this.additionalTaskView);
  },
  terminal: function()
  {
    if (!this.terminalView) {
      this.terminalView = new TerminalView();
    }

    this.selectView(this.terminalView);
  },
  camera: function()
  {
    if (!this.cameraView) {
      this.cameraView = new CameraView();
    }

    this.selectView(this.cameraView);
    app.selectQuickNav('camera');
  },
  selectView: function(view)
  {
    var currentView = app.$el.find('.app-view.active');
    var targetView = view.$el;
    var targetId = targetView.attr('id');

    targetView.removeClass('hide').addClass('active');
    targetView.trigger('show');

    if (targetView.data('fullscreen')) {
      $('#app').addClass('hide');

      currentView.each(function(idx, el) {
        var $el = $(el);

        if ($el.attr('id') != targetId && $el.data('fullscreen')) {
          //If we have another fullscreen view, hide it
          $el.addClass('hide').removeClass('active');
        }
      });

      currentView.trigger('hide');
    } else {
      if (currentView.attr('id') != targetId) {
        currentView.addClass('hide').removeClass('active');
        currentView.trigger('hide');

        if (targetId == 'utilities-view') {
          this.utilitiesView.tempView.show();
          this.utilitiesView.extrusionView.render();
        }
      }

      app.selectQuickNav();
    }
  },
  notFound: function()
  {
    this.navigate("", {trigger: true, replace: true});
  },
  supplies: function()
  {
    if (!this.suppliesView) {
      this.suppliesView = new SuppliesView();
    }

    this.selectView(this.suppliesView);
  },
  help: function()
  {
    if (!this.helpView) {
      this.helpView = new HelpView();
    }

    this.selectView(this.helpView);
  },

  // View Loading outside of navigation
  loadFilesView: function(syncCloud)
  {
    if (this.filesView) {
      return true;
    } else {
      var promise = $.Deferred();

      this.filesView = new FilesView({forceSync: syncCloud, syncCompleted: function(success) {
        if (success) {
          promise.resolve()
        } else {
          promise.reject('unable_to_refresh');
        }
      }});

      return promise;
    }

  }
});
