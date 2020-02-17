/*
 *  (c) AstroPrint Product Team. 3DaGoGo, Inc. (product@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

/* global PrintFileCollection, USBFileCollection */

/* exported FilesView */

var PrintFileInfoDialog = Backbone.View.extend({
  el: '#print-file-info',
  file_list_view: null,
  template: _.template( $("#printfile-info-template").html() ),
  print_file_view: null,
  queueAllowed: false,
  events: {
    'click .actions a.remove': 'onDeleteClicked',
    'click .actions a.print': 'onPrintClicked',
    'click .actions a.queue': 'onAddToQueueClicked',
    'click .actions a.download': 'onDownloadClicked'
  },
  initialize: function(params)
  {
    this.file_list_view = params.file_list_view;
    this.queueAllowed = params.queueAllowed;
  },
  render: function()
  {
    this.$el.find('.dlg-content').html(this.template({
      p: this.print_file_view.print_file.toJSON(),
      queueAllowed: this.queueAllowed,
      time_format: app.utils.timeFormat
    }));
  },
  open: function(print_file_view)
  {
    this.print_file_view = print_file_view;
    this.render();
    this.$el.foundation('reveal', 'open');
  },
  onDeleteClicked: function(e)
  {
    e.preventDefault();

    var print_file = this.print_file_view.print_file;

    if (print_file) {
      var filename = print_file.get('local_filename');
      var loadingBtn = $(e.currentTarget).closest('.loading-button');

      loadingBtn.addClass('loading');
      $.ajax({
        url: '/api/files/local/'+filename,
        type: "DELETE",
        success: _.bind(function() {
          //Update model
          if (print_file.get('local_only')) {
            this.file_list_view.file_list.remove(print_file);
          } else {
            print_file.set('local_filename', false);
            print_file.set('uploaded_on', null);
          }

          noty({text: filename+" deleted from your "+PRODUCT_NAME, type:"success", timeout: 3000});
          this.print_file_view.render();
          this.$el.foundation('reveal', 'close');
        }, this),
        error: function() {
          noty({text: "Error deleting "+filename, timeout: 3000});
        },
        always: function() {
          loadingBtn.removeClass('loading');
        }
      });
    }
  },
  onAddToQueueClicked: function(e)
  {
    e.preventDefault()

    this.print_file_view.doAddToQueue().then()
      .done(_.bind(function () {
        this.file_list_view.doSync();
      }, this))
  },
  onPrintClicked: function(e)
  {
    this.print_file_view.printClicked(e);
    this.$el.foundation('reveal', 'close');
  },
  onDownloadClicked: function(e)
  {
    this.print_file_view.downloadClicked(e);
    this.$el.foundation('reveal', 'close');
  }
});

var FileUploadFiles = FileUploadCombined.extend({
  progressBar: null,
  buttonContainer: null,
  initialize: function(options)
  {
    this.progressBar = options.progressBar;
    this.buttonContainer = options.buttonContainer;

    FileUploadCombined.prototype.initialize.call(this, options);
  },
  started: function(data)
  {
    if (data.files && data.files.length > 0) {
      this.buttonContainer.hide();
      this.progressBar.show();
      FileUploadCombined.prototype.started.call(this, data);
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
  onError: function(type, error)
  {
    var message = error;

    switch(error) {
      //case 'invalid_data':
      //case 'http_error_400':
      //break;

      case 'http_error_401':
        message = 'An AstroPrint account is needed to upload designs';
        $('#login-modal').foundation('reveal', 'open');
      break;

      case null:
        message = 'There was an error uploading your file';
      break;
    }

    noty({text: message, timeout: 3000});
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

var UploadView = Backbone.View.extend({
  uploadBtn: null,
  progressBar: null,
  buttonContainer: null,
  initialize: function(options)
  {
    this.progressBar = this.$('.upload-progress');
    this.buttonContainer = this.$('.upload-buttons');

    this.uploadBtn = new FileUploadFiles({
      el: "#files-view .file-upload-view .file-upload",
      progressBar: this.$('.upload-progress'),
      buttonContainer: this.$('.file-upload-button'),
      dropZone: options.dropZone
    });

    this.render();
  },
  render: function()
  {
    var buttonContainer = this.$('.file-upload-button');

    if (app.printerProfile.get('driver') == 's3g') {
      buttonContainer.find('.extensions').text('stl, x3g');
      buttonContainer.find('input').attr('accept', '.stl, .x3g');
    } else {
      buttonContainer.find('.extensions').text('stl, gcode');
      buttonContainer.find('input').attr('accept', '.stl, .gcode, .gco');
    }

    this.uploadBtn.refreshAccept();
  }
});

var PrintFileView = Backbone.View.extend({
  template: _.template( $("#print-file-template").html() ),
  print_file: null,
  list: null,
  printWhenDownloaded: false,
  downloadProgress: null,
  queueAllowed: false,
  launchingAp : false,
  events: {
    'click .left-section, .middle-section': 'infoClicked',
    'click a.print': 'printClicked',
    'click a.queue': 'addToQueueClicked',
    'click a.download': 'downloadClicked',
    'click a.dw-cancel': 'cancelDownloadClicked'
  },
  initialize: function(options)
  {
    this.list = options.list;
    this.print_file = options.print_file;
    this.queueAllowed = options.queueAllowed;
  },
  slideName: function () {
    if (!this.$(".div-container").size() || this.$(".div-container").width()<=0) {
      setTimeout(_.bind(this.slideName,this), 500); // give everything some time to render
    } else {
      if(this.$('.text').width() >= this.$('.div-container').width()){
        this.$('.text').addClass('slide-text')
      } else {
        this.$('.text').removeClass('slide-text')
      }
    }
  },
  render: function()
  {
    var print_file = this.print_file.toJSON();

    if (print_file.local_filename) {
      this.$el.removeClass('remote');
    } else {
      this.$el.addClass('remote');
    }

    if (print_file.printFileName) {
      print_file.name = print_file.printFileName;
    }

    this.$el.empty();
    this.downloadProgress = null;
    this.$el.html(this.template({
      p: print_file,
      queueAllowed: this.queueAllowed,
      time_format: app.utils.timeFormat,
      size_format: app.utils.sizeFormat
    }));

    $.localtime.format(this.$('.info-container'));

    this.slideName();
  },
  infoClicked: function(evt)
  {
    if (evt) evt.preventDefault();
    this.list.info_dialog.open(this);
  },
  downloadClicked: function(evt)
  {
    if (evt) evt.preventDefault();

    $.getJSON('/api/astroprint/print-files/'+this.print_file.get('id')+'/download')
      .fail(function(){
        noty({text: "There was an error starting the download.", timeout: 3000});
      });
  },
  cancelDownloadClicked: function(evt)
  {
    evt.preventDefault();

    $.ajax({
      url: '/api/astroprint/print-files/'+this.print_file.get('id')+'/download',
      method: 'DELETE'
    })
      .fail(function() {
        noty({text: "Unable to cancel download.", timeout: 3000});
      });
  },
  printClicked: function (evt)
  {
    if (evt) evt.preventDefault();

    var filename = this.print_file.get('local_filename');

    if (filename) {
      if ( !app.printerProfile.get('printer_model').id || this.$el.parent().parent().hasClass('design-filtered-list')) {
        this.doPrint(filename);
      } else {
        if (!this.print_file.get('printer') || this.print_file.get('printer')['model_id']) {
          this.doPrint(filename);
        } else {
          (new noPrintDialog()).open({printFilePrinterName: this.print_file.get('printer')['name']})
        }
      }
    } else {
      //We need to download and print
      this.printWhenDownloaded = true;
      this.downloadClicked();
    }
  },
  doPrint: function(filename)
  {
    //We can't use evt because this can come from another source than the row print button
    var loadingBtn = this.$('.loading-button.print');
    loadingBtn.addClass('loading');
    $.ajax({
        url: '/api/files/local/'+filename,
        type: "POST",
        dataType: "json",
        contentType: "application/json; charset=UTF-8",
        data: JSON.stringify({command: "select", print: true})
    })
    .done(_.bind(function() {
      setTimeout(function(){
        loadingBtn.removeClass('loading');
      },2000);
    }, this))
    .fail(function(xhr) {
      var error = null;
      if (xhr.status == 409) {
        error = xhr.responseText;
      }
      noty({text: error ? error : "There was an error starting the print", timeout: 3000});
      loadingBtn.removeClass('loading');
    })
  },
  addToQueueClicked: function(evt)
  {
    evt.preventDefault();

    if (!app.printerProfile.get('printer_model').id || !this.print_file.get('printer') || this.print_file.get('printer')['model_id']) {
      this.doAddToQueue().then()
        .done(_.bind(function () {
          this.list.doSync()
        }, this))
    } else {
      (new noPrintDialog()).open({ printFilePrinterName: this.print_file.get('printer')['name'] })
    }
  },
  doAddToQueue: function()
  {
    var promise = $.Deferred();
    var loadingBtn = this.$('.loading-button.queue');
    loadingBtn.addClass('loading');

    app.astroprintApi.addElemenToQueue(this.print_file.get('id'))
      .done(_.bind(function () {
        noty({ text: "File successfully added to the queue", type: 'success', timeout: 3000 });
        promise.resolve();
      }, this))

      .fail(_.bind(function (xhr) {
        console.error('File failed to be added to the queue', xhr);
        noty({ text: "File failed to be added to the queue", timeout: 3000 });
        promise.reject();
      }, this))

    return promise;
  }
});

var StorageControlView = Backbone.View.extend({
  print_file_view: null,
  events: {
    'click a.USB': 'usbClicked',
    'click a.local': 'localClicked',
    'click a.cloud': 'cloudClicked'
  },
  selected: null,
  exploringLocation: null,
  initialize: function(options)
  {
    this.print_file_view = options.print_file_view;
    //local default selection
    this.$('a.active').removeClass('active');
    this.$('a.local').addClass('active');
    this.selected = 'local';
  },
  _cleanUrlNavigation: function(location){
    return location.replace(/\/+/g, "/");
  },
  composeLocation: function(locationNavigation)
  {
    if(locationNavigation != 'back'){
      if(this.exploringLocation != '/'){
        this.exploringLocation = this._cleanUrlNavigation(locationNavigation);
      } else {
        this.exploringLocation = this._cleanUrlNavigation(this.exploringLocation + locationNavigation);
      }
    } else { //BACK
      if(!this.print_file_view.usbfile_list.topLocationMatched(this.exploringLocation)){
        this.exploringLocation = this.exploringLocation.substr(0, this.exploringLocation.lastIndexOf('/'));
      } else {//TOP LOCATION
        this.exploringLocation = '/';
      }
    }
  },
  selectStorage: function(storage)
  {
    this.$('a.active').removeClass('active');
    this.$('a.'+storage).addClass('active');
    this.$('div.list-header').removeClass(this.selected)
    this.selected = storage;
    this.$('div.list-header').addClass(this.selected)
    this.print_file_view.render();
  },
  usbClicked: function(e)
  {
    e.preventDefault();
    $('h3.printablefiles-message').addClass('hide');
    this.print_file_view.showRemovableDrives();
    this.selectStorage('USB');
  },
  localClicked: function(e)
  {
    e.preventDefault();
    $('h3.printablefiles-message').removeClass('hide');
    this.selectStorage('local');
  },
  cloudClicked: function(e)
  {
    e.preventDefault();
    $('h3.printablefiles-message').removeClass('hide')

    if (LOGGED_USER) {
      if(ON_FLEET){
        if (!this.launchingAp) {
          this.launchingAp = true;
          $.getJSON(API_BASEURL+'astroprint/login-key')
            .done(function(data){
              const url =  'https://www.astroprint.com/account/loginKey/'+data.login_key + "?redirect=files&fleetpage=true"
              const win = window.open(url, '_blank')
              win.focus();
            })
            .fail(function(){
              location.href = AP_API_HOST +'https://www.astroprint.com/account/login'
            })
            .always(_.bind(function(){
              this.launchingAp = false;
            }, this));
        }
      } else {
        this.selectStorage('cloud')
      }
    } else {
      $('#login-modal').foundation('reveal', 'open')
    }
  }
});

var PrintFilesListView = Backbone.View.extend({
  info_dialog: null,
  external_removed_warning_dlg: null,
  print_file_views: [],
  usb_file_views: [],
  storage_control_view: null,
  file_list: null,
  usbfile_list: null,
  refresh_threshold: 1000, //don't allow refreshes faster than this (in ms)
  last_refresh: 0,
  refreshing: false,
  need_to_be_refreshed: false,
  filesOnQueue: 0,
  queueAllowed: false,
  mainView: null,
  events: {
    'click .list-header button.sync': 'onSyncClicked'
  },
  initialize: function(options) {
    this.mainView = options.mainView;
    this.file_list = new PrintFileCollection();
    this.storage_control_view = new StorageControlView({
      el: this.$('.list-header ul.storage'),
      print_file_view: this
    });

    app.eventManager.on('astrobox:cloudDownloadEvent', this.downloadProgress, this);
    app.eventManager.on('astrobox:MetadataAnalysisFinished', this.onMetadataAnalysisFinished, this);
    app.eventManager.on('astrobox:externalDriveMounted', this.externalDrivesChanged, this);
    app.eventManager.on('astrobox:externalDriveEjected', this.externalDrivesChanged, this);
    app.eventManager.on('astrobox:externalDrivePhisicallyRemoved', this.externalDrivesChanged, this);

    this.listenTo(this.file_list, 'remove', this.onFileRemoved);

    this.getFilesOnQueue().then()
    .done(_.bind(function (filesOnQueue) {
      if (filesOnQueue != "no_queue_allowed") {
        this.filesOnQueue = filesOnQueue;
        this.queueAllowed = true;
      } else {
        this.queueAllowed = false;
      }
      this.refresh('local', options.syncCompleted);
      this.info_dialog = new PrintFileInfoDialog({ queueAllowed: this.queueAllowed, file_list_view: this });
      this.usbfile_list = new USBFileCollection();
    }, this))
    .fail(_.bind(function (e) {
      console.error(e);
    }, this))

  },
  showRemovableDrives: function()
  {
    this.storage_control_view.exploringLocation = '/';
    this.externalDrivesRefresh();
  },
  externalDrivesChanged: function(data)
  {
    switch(data.action) {
      case 'mounted':
        this.usbfile_list.onDriveAdded(data.mount_path);
      break;

      case 'ejected':
        this.usbfile_list.onDriveRemoved(data.mount_path);
      break;

      case 'removed':
        if (this.usbfile_list.isMounted(data.mount_path)) {
          this.usbfile_list.onDriveRemoved(data.mount_path);
          if (!this.external_removed_warning_dlg) {
            this.external_removed_warning_dlg = new ExternalRemovedWarningDlg();
          }

          this.external_removed_warning_dlg.open();
        }
    }

    this.externalDrivesRefresh();
  },
  externalDrivesRefresh: function()
  {
    var path = this.storage_control_view.exploringLocation;

    this.$('.loading-button.sync').addClass('loading');
    return this.usbfile_list.syncLocation(path)
      .done(_.bind(function(){
        this.usb_file_views = [];

        if(path != '/'){
          var backView = new BackFolderView(
            {
              parentView: this
            });
            backView.render();
          this.usb_file_views.push(backView);
        }

        this.usbfile_list.each(_.bind(function(file/*, idx*/) {
          var usb_file_view = null
          if(this.usbfile_list.extensionMatched(file.get('name'))) {
            usb_file_view = new USBFileView(file, this);
          } else {
            usb_file_view = new BrowsingFileView(
              {
                parentView: this,
                file: file
              });
          }

          this.usb_file_views.push( usb_file_view );

        }, this));

        this.render();
      },this))
      .fail(function(){
        noty({text: "There was an error retrieving files in the drive", timeout: 3000});
      })
      .always(_.bind(function(){
        this.$('.loading-button.sync').removeClass('loading');
      },this))
  },
  render: function()
  {
    var listNoFilteredEl = this.$('.design-list');
    var listNoFilteredContainer = listNoFilteredEl.find('.container-files');

    var listFilteredEl = this.$('.design-filtered-list');
    var listFilteredContainer = listFilteredEl.find('.container-files');

    var selectedStorage = this.storage_control_view.selected;

    listNoFilteredContainer.empty();
    listFilteredContainer.empty();

    if (selectedStorage == 'USB') { //CLICKED IN THE USB TAB
      //CLEAN FILE LIST SHOWED
      this.$('.header-filter').hide();
      listFilteredEl.hide()

      if (this.usb_file_views.length) {
        _.each(this.usb_file_views, function (p) {
          listNoFilteredContainer.append(p.$el);
          p.render();
        });

        if (this.usb_file_views.length == 1 && this.usb_file_views[0] instanceof BackFolderView) {
          listNoFilteredContainer.append(
            '<div class="empty panel row clearfix radius" align="center">' +
            ' <i class="icon-inbox empty-icon"></i>' +
            ' <h3>No Printable files.</h3>' +
            '</div>'
          );
        }
      } else {
        listNoFilteredContainer.append(
          '<div class="empty panel row clearfix radius" align="center">' +
          ' <i class="icon-inbox empty-icon"></i>' +
          ' <h3>No External Drives Connected.</h3>' +
          '</div>'
        );
      }

    } else {
      if (selectedStorage) {
        if(this.need_to_be_refreshed && selectedStorage == 'local'){
          this.refresh('local');
          this.need_to_be_refreshed = false;
        } else {
          var unmatchedFileViews = null;
          var matchedFileViews = null;
          if (selectedStorage == 'cloud') {
            unmatchedFileViews = [];
            matchedFileViews = _.filter(this.print_file_views, function(p){
              if (!p.print_file.get('local_only') && p.print_file.get('printer') && p.print_file.get('printer').model_id == app.printerProfile.get('printer_model').id) {
                return true;
              } else if (!p.print_file.get('local_only')) {
                unmatchedFileViews.push(p)
                return false;
              }
              return false
            });
          } else {
            // here ?
            unmatchedFileViews = []
            matchedFileViews = _.filter(this.print_file_views, function (p) {
              if (p.print_file.get('local_filename')) {
                if (p.print_file.get('printer') && p.print_file.get('printer').model_id == app.printerProfile.get('printer_model').id) {
                  return true;
                } else {
                  unmatchedFileViews.push(p)
                  return false;
                }
              }
            });
          }
        }
      } else {
        matchedFileViews = this.print_file_views;
      }

      var matchedFilesFound = false;
      var unmatchedFilesFound = false;
      // Matched files
      if (matchedFileViews && matchedFileViews.length) {
        listFilteredEl.find('.header-filter').show();
        listFilteredEl.show();
        _.each(matchedFileViews, function(p) {
          listFilteredContainer.append(p.$el);
          p.delegateEvents();
        });
        matchedFilesFound = true;
      } else {
        listFilteredEl.find('.header-filter').hide();
        listFilteredEl.hide()
      }

      // Unmatched files
      if (unmatchedFileViews && unmatchedFileViews.length) {
        listNoFilteredEl.find('.header-filter').show();
        _.each(unmatchedFileViews, function(p) {
          listNoFilteredContainer.append(p.$el);
          p.delegateEvents();
        });
        unmatchedFilesFound = true;
      } else {
        listNoFilteredEl.find('.header-filter').hide();
      }

      // If no cloud tab or no printer model stored, hide headers and filter container
      if (selectedStorage == "USB" || !app.printerProfile.get('printer_model').id) {
        this.$('.header-filter').hide();
        listFilteredEl.hide()
      }

      // Update printer model name
      if (app.printerProfile.get('printer_model').id) {
        this.$('.printer-name').text(app.printerProfile.get('printer_model').name);
      }

      // No files => show Empty Template
      if (!matchedFilesFound && !unmatchedFilesFound) {
        listNoFilteredContainer.html(
          '<div class="empty panel row clearfix radius" align="center">'+
          ' <i class="icon-inbox empty-icon"></i>'+
          ' <h3>Nothing here yet.</h3>'+
          '</div>');
          listNoFilteredEl.find('.header-filter').hide()
      }
    }

    if (!this.queueAllowed) {
      this.$el.removeClass('queued')
    } else {
      this.$el.addClass('queued')
      this.$('#files-on-queue .counter-queue').text(this.filesOnQueue);
    }
  },
  refresh: function(kindOfSync, doneCb)
  {
    var now = new Date().getTime();

    if (this.last_refresh == 0 || this.last_refresh < (now - this.refresh_threshold) ) {
      this.last_refresh = now;

      if ( !this.refreshing ) {
        this.refreshing = true;
        var loadingArea = null;
        var syncPromise = null;

        switch(kindOfSync){
          case 'cloud':
            loadingArea = this.$('.loading-button.sync');
            syncPromise = this.file_list.syncCloud();
          break;

          case 'local':
            loadingArea = this.$('.local-loading');
            syncPromise = this.file_list.fetch();
          break;
        }

        loadingArea.addClass('loading');
        return syncPromise
          .done(_.bind(function(){
            this.print_file_views = [];
            this.file_list.each(_.bind(function(print_file) {
              var print_file_view = new PrintFileView({
                list: this,
                print_file: print_file,
                queueAllowed: this.queueAllowed,
                attributes: {'class': 'row'}
              });
              print_file_view.render();
              this.print_file_views.push( print_file_view );
            }, this));

            this.$('.design-list .container-files').empty();
            this.render();

            if (_.isFunction(doneCb)) {
              doneCb(true);
            }
            loadingArea.removeClass('loading');

            this.refreshing = false;
          }, this))
          .fail(_.bind(function(){
            noty({text: "There was an error retrieving print files", timeout: 3000});

            if (_.isFunction(doneCb)) {
              doneCb(false);
            }

            loadingArea.removeClass('loading');
            this.refreshing = false;
          }, this));
      }
    }
  },
  downloadProgress: function(data)
  {
    var print_file_view = _.find(this.print_file_views, function(v) {
      return v.print_file.get('id') == data.id;
    });

    if (print_file_view) {
      var progressContainer = print_file_view.$('.print-file-options');

      switch (data.type) {
        case 'progress':
        {
          if (!progressContainer.hasClass('downloading')) {
            progressContainer.addClass('downloading');
          }

          if (!print_file_view.downloadProgress) {
            var progress = progressContainer.find('.download-progress');

            print_file_view.downloadProgress = progress.circleProgress({
              value: 0,
              animation: false,
              size: progressContainer.innerWidth(),
              fill: { color: 'black' }
            });
          } else {
            print_file_view.downloadProgress.circleProgress({value: data.progress / 100.0});
          }

          var label = print_file_view.$('.download-progress span');

          label.html(Math.floor(data.progress) + '<i>%</i>');
        }
        break;

        case 'success':
        {
          var print_file = print_file_view.print_file;

          if (print_file) {
            print_file.set('local_filename', data.filename);
            print_file.set('print_time', data.print_time);
            print_file.set('layer_count', data.layer_count);
            print_file.set('uploaded_on', Date.now() / 1000);

            print_file_view.render();

            if (print_file_view.printWhenDownloaded) {
              print_file_view.printWhenDownloaded = false;
              print_file_view.printClicked();
            }
          }
        }
        break;

        case 'error':
        {
          progressContainer.removeClass('downloading').addClass('failed');
          console.error('Error downloading file: '+data.reason);
          setTimeout(function(){
            progressContainer.removeClass('failed');
          },3000);
        }
        break;

        case 'cancelled':
        {
          progressContainer.removeClass('downloading');
        }
        break;
      }
    }
  },
  onSyncClicked: function(e)
  {
    e.preventDefault();
    this.doSync();
  },
  doSync: function()
  {
    var loadingArea = this.$('.local-loading');
    loadingArea.addClass("loading");
    this.getFilesOnQueue().then()
      .done(_.bind(function (filesOnQueue) {
        if (filesOnQueue != "no_queue_allowed") {
          this.filesOnQueue = filesOnQueue;
          this.queueAllowed = true;
        } else {
          this.filesOnQueue = 0;
          this.queueAllowed = false;
        }

        if (this.info_dialog) {
          this.info_dialog.queueAllowed = this.queueAllowed
        }

        // Sync
        switch (this.storage_control_view.selected) {
          case 'USB':
            this.externalDrivesRefresh().always(function(){loadingArea.removeClass("loading")});
            break;

          case 'cloud':
            this.refresh('cloud').always(function(){loadingArea.removeClass("loading")});
          case 'local':
            this.refresh('cloud').always(function(){loadingArea.removeClass("loading")});
        }
      }, this));

  },
  getFilesOnQueue: function ()
  {
    var promise = $.Deferred();

    if (initial_states.userLogged) {
      this.hasQueueAccess()
        .done(_.bind(function (hasQueueAccess) {
          if (hasQueueAccess) {
            this.loadQueue()
              .done(_.bind(function (data) {
                var filesOnQueue = data ? data.ready_counter : 0;
                promise.resolve(filesOnQueue)
              }, this))
              .fail(_.bind(function () {
                noty({ text: "Something went wrong when get Queue information", timeout: 3000 });
                promise.resolve(0);
              }, this));
          } else {
            promise.resolve("no_queue_allowed"); // No queue_allowed, if 0 not showing queue UI
          }
        }, this))
        .fail(_.bind(function () {
          noty({ text: "Something went wrong when checking permission to use Queues", timeout: 3000 });
          promise.resolve(0);
        }, this));
    } else {
      promise.resolve(0);
    }
    return promise;
  },
  hasQueueAccess: function()
  {
    var promise = $.Deferred();

    app.astroprintApi.me()
      .done(function (user) {
        var hasQueueAccess = user.plan ? user.plan.queues_allowed : false;
        promise.resolve(hasQueueAccess);
      })
      .fail(function (xhr) {
        console.error(xhr.statusText)
        promise.reject(xhr.statusText);
      })

      return promise;
  },
  loadQueue: function()
  {
    var promise = $.Deferred();

    app.astroprintApi.queue()
      .done(_.bind(function (data) {
        promise.resolve(data);
      }, this))

      .fail(_.bind(function (xhr) {
        console.error(xhr);
        promise.reject(xhr);
      }, this))

    return promise;
  },
  onFileRemoved: function(print_file)
  {
    //Find the view that correspond to this print file
    var view = _.find(this.print_file_views, function(v) {
      return v.print_file == print_file;
    });

    if (view) {
      //Remove from DOM
      view.remove();

      //Remove from views array
      this.print_file_views.splice(this.print_file_views.indexOf(view), 1);
    }
  },
  onMetadataAnalysisFinished: function(data)
  {
    _.each(this.print_file_views, function(p) {
      if (p.print_file.get('local_filename') == data.file) {
        p.print_file.set('info', data.result);
        p.render();
        return;
       }
    });
  },
  onPrinterDriverChanged: function()
  {
    this.usbfile_list.refreshExtensions().done(_.bind(function(){
      this.doSync();
    },this));
  }
});

var FilesView = Backbone.View.extend({
  el: '#files-view',
  uploadView: null,
  printFilesListView: null,
  events: {
    'show': 'onShow'
  },

  onShow: function()
  {
    this.printFilesListView.doSync();
  },

  initialize: function(options)
  {
    this.uploadView = new UploadView({
      el: this.$el.find('.file-upload-view'),
      dropZone: this.$el
    });
    this.printFilesListView = new PrintFilesListView({
      el: this.$('.design-list'),
      forceSync: options.forceSync,
      syncCompleted: options.syncCompleted
    });

    this.listenTo(app.printerProfile, 'change:driver', this.onDriverChanged);
  },
  refreshPrintFiles: function()
  {
    var promise = $.Deferred();
    this.printFilesListView.refresh('cloud', function(success) {
      if (success) {
        promise.resolve();
      } else {
        promise.reject('unable_to_refresh');
      }
    });

    return promise;
  },
  fileInfo: function(fileId)
  {
    var view = _.find(this.printFilesListView.print_file_views, function(v) {
      return v.print_file.get('id') == fileId;
    });

    this.printFilesListView.storage_control_view.selectStorage('cloud');
    this.showFileInfoView(view);
  },
  fileInfoByName: function(name)
  {
    var view = _.find(this.printFilesListView.print_file_views, function(v) {
      return v.print_file.get('name') == name;
    });

    this.showFileInfoView(view);
  },
  showFileInfoView: function(view)
  {
    if (view) {
      view.infoClicked();
    }
  },
  onDriverChanged: function()
  {
    this.uploadView.render();
    this.printFilesListView.refresh('cloud');
  }
});

var ExternalRemovedWarningDlg = Backbone.View.extend({
  el: '#external-removed-warning-dlg',
  events: {
    "click button.close": "onCloseClicked"
  },
  open: function()
  {
    this.$el.foundation('reveal', 'open');
  },
  onCloseClicked: function(e)
  {
    e.preventDefault();
    this.$el.foundation('reveal', 'close');
  }
});

var ReplaceFileDialog = Backbone.View.extend({
  el: '#local-file-exists-dlg',
  filename: null,
  usbFileView: null,
  copyFinishedPromise: null,
  template: _.template( $("#local-file-exists-template").html() ),
  events: {
    'click button.replace': 'onReplaceClicked',
    'click button.cancel': 'onCancelClicked',
    'closed.fndtn.reveal': 'onClose'
  },
  render: function()
  {
    this.$('.dlg-content').html(this.template({
      filename: this.filename
    }));
  },
  open: function(options)
  {
    this.usbFileView = options.usbFileView;
    this.filename = options.filename;
    this.copyFinishedPromise = options.copyFinishedPromise;
    this.render();
    this.$el.foundation('reveal', 'open');
  },
  onReplaceClicked: function(e)
  {
    if(e) e.preventDefault();

    this.$el.foundation('reveal', 'close');
    this.usbFileView.copyFile(this.copyFinishedPromise);
  },
  onCancelClicked: function(e)
  {
    if(e) e.preventDefault();

    this.$el.foundation('reveal', 'close');
    this.copyFinishedPromise.reject('replace_canceled');
  },
  onClose: function(){
    this.usbFileView.$('button.copy').removeClass('hide');
    this.usbFileView.$('button.print').removeClass('hide');
    this.$('.dlg-content').empty();
    this.undelegateEvents();
    this.usbFileView = null;
    this.filename = null;
    this.copyFinishedPromise = null;
  }
});

var noPrintDialog = Backbone.View.extend({
  el: '#no-print-dlg',
  printFilePrinterName: null,
  template: _.template( $("#no-print-template").html() ),
  events: {
    'closed.fndtn.reveal': 'onClose',
    'click button.cancel': 'onCancelClicked'
  },
  render: function()
  {
    this.$('.dlg-content').html(this.template({
      printFilePrinterName: this.printFilePrinterName,
      astroboxPrinterName: app.printerProfile.get('printer_model').name
    }));
  },
  open: function(options)
  {
    this.printFilePrinterName = options.printFilePrinterName;

    this.render();
    this.$el.foundation('reveal', 'open');
  },
  onCancelClicked: function(e)
  {
    e.preventDefault()
    this.$el.foundation('reveal', 'close');
  },
  onClose: function(){
    this.$('.dlg-content').empty();
    this.undelegateEvents();
    this.printFilePrinterName = null;
  }
});

var USBFileView = Backbone.View.extend({
  template: _.template( $("#usb-file-template").html() ),
  usb_file: null,
  copying: null,
  progress: -1,
  parentView: false,
  events: {
    'click button.copy': 'copyClicked',
    'click button.print': 'printClicked'
  },
  initialize: function(file, parentView)
  {
    this.usb_file = file;
    this.parentView = parentView;
  },
  render: function()
  {
    this.$el.html(this.template({
      name: this.usb_file.get('name').split('/').splice(-1,1)[0],
      size: this.usb_file.get('size'),
      size_format: app.utils.sizeFormat
    }));

    this.slideName();
    this.delegateEvents();
  },
  slideName: function () {
    if (!this.$(".div-container").size() || this.$(".div-container").width()<=0) {
      setTimeout(_.bind(this.slideName,this), 500); // give everything some time to render
    } else {
      if(this.$('.text').width() >= this.$('.div-container').width()){
        this.$('.text').addClass('slide-text')
      } else {
        this.$('.text').removeClass('slide-text')
      }
    }
  },
  startPrint: function()
  {
    var filename = this.usb_file.get('secure_filename')
    if (!filename) {
      filename = this.usb_file.get('name')
    }

    filename = filename.split('/').splice(-1,1)[0];

    //We can't use evt because this can come from another source than the row print button
    var loadingBtn = this.$('.loading-button.print');

    loadingBtn.addClass('loading');
    $.ajax({
        url: '/api/files/local/'+filename,
        type: "POST",
        dataType: "json",
        contentType: "application/json; charset=UTF-8",
        data: JSON.stringify({command: "select", print: true})
    })
    .done(_.bind(function() {
      setTimeout(function(){
        loadingBtn.removeClass('loading');
      }, 2000);
    }, this))
    .fail(function(xhr) {
      var error = null;
      if (xhr.status == 409) {
        error = xhr.responseText;
      }
      noty({text: error ? error : "There was an error starting the print", timeout: 3000});
      loadingBtn.removeClass('loading');
    })
  },
  printClicked: function(evt)
  {
    if (evt) evt.preventDefault();

    this.tryToCopyFile()
      .done(_.bind(function(filename){

        this.usb_file.set('secure_filename', filename)

        var dlg = new EjectBeforePrintDialog();
        var filePath = this.usb_file.get('name');

        dlg.open({
          drive: filePath.substr(0,filePath.lastIndexOf('/')),
          fileView: this,
          fileListView: this.parentView
        });

      },this))
      .fail(function(err){
        if (err && err !='replace_canceled') {
          noty({text: "Print can not be starterd. Try it again later", timeout: 3000});
        }
      });
  },
  copyToHomeProgressUpdater: function(data){
    this.progress = data.progress.toFixed(1);

    this.$('.loading-content').html(_.template( $("#copy-to-home-progress").html() )({
      progress: this.progress
    }));
  },
  copyClicked: function (evt)
  {
    if (evt) evt.preventDefault();

    this.$('button.copy').addClass('hide')
    this.$('button.print').addClass('hide')

    this.tryToCopyFile()
      .done(_.bind(function(){
        this.$('button.copy').removeClass('hide')
        this.$('button.print').removeClass('hide')
      },this))
      .fail(_.bind(function(){
        this.$('button.copy').removeClass('hide')
        this.$('button.print').removeClass('hide')
      },this));
  },
  copyFile: function(promise){

    var filename = this.usb_file.get('name');

    app.eventManager.on('astrobox:copyToHomeProgress', this.copyToHomeProgressUpdater, this);

    var loadingBtn = this.$('.loading-button.print');

    loadingBtn.addClass('loading');

    $.ajax({
      url: '/api/files/copy-to-local',
      type: "POST",
      dataType: "json",
      data:
        {
          file: filename,
          observerId: AP_SESSION_ID
        }
    })
    .done(_.bind(function(data) {
      if(!data.filename){
        noty({text: "There was an error copying file...Try it again later", timeout: 3000});
        promise.reject();
      } else {
        noty({text: filename.substr(filename.lastIndexOf('/')+1) + " copied to internal storage.",type: 'success',timeout: 3000});
        this.parentView.need_to_be_refreshed = true;
        promise.resolve(data.filename);
      }
      loadingBtn.removeClass('loading');
    }, this))
    .fail(_.bind(function() {
      noty({text: "There was an error copying file...Try it again later", timeout: 3000});
      promise.reject();
    },this))
    .always(_.bind(function() {
      loadingBtn.removeClass('loading');
      this.$el.foundation('reveal', 'close');
      this.$('button.copy').removeClass('hide')
      this.$('button.print').removeClass('hide')
      app.eventManager.off('astrobox:copyToHomeProgress', this.copyToHomeProgressUpdater, this);
      this.$('.loading-content').html('');
    }, this));
  },
  tryToCopyFile: function(){
    var promise = $.Deferred();

    var filename = this.usb_file.get('name').split('/').splice(-1,1)[0];

    $.getJSON('/api/files/local-file-exists/' + filename)
      .success(_.bind(function(data){
        if(data.response){
          var dlg = new ReplaceFileDialog();

          dlg.open({
            usbFileView: this,
            filename: filename,
            copyFinishedPromise: promise
          });
        } else {
          this.copyFile(promise);
        }
      },this))
      .fail(_.bind(function(){
        noty({text: "There was an error copying selecte file. Try it again later.", timeout: 3000});
        this.$('button.copy').removeClass('hide');
        this.$('button.print').removeClass('hide');
        promise.reject();
      }, this));

    return promise;
  }
});

var EjectBeforePrintDialog = Backbone.View.extend({
  el: '#eject-before-print-dlg',
  drive: null,
  fileView: null,
  fileListView: null,
  template: _.template( $("#eject-before-print-template").html() ),
  events: {
    'click button.eject-no': 'onNoClicked',
    'click button.eject-yes': 'onYesClicked',
    'closed.fndtn.reveal': 'onClose'
  },
  render: function()
  {
    this.$('.dlg-content').html(this.template({
      filename: this.filename
    }));
  },
  open: function(options)
  {
    this.drive = options.drive;
    this.fileView = options.fileView;
    this.fileListView = options.fileListView;
    this.render();
    this.$el.foundation('reveal', 'open');
  },
  onYesClicked: function(e)
  {
    if(e) e.preventDefault();

    var loadingBtn = $(e.currentTarget).closest('.loading-button');
    loadingBtn.addClass('loading');

    $.ajax({
        url: '/api/files/eject',
        type: "POST",
        dataType: "json",
        data: {
          drive: this.drive
        }
    })
    .done(_.bind(function(data) {
      if(data && data.error){
        var error = data.error
        noty({text: "There was an error ejecting drive" + (error ? ': ' + error : ""), timeout: 3000});
      } else {
        this.fileListView.showRemovableDrives();
        this.fileView.startPrint();
        setTimeout(function(){
          noty({text: "Drive ejected. You can safely remove the external drive.<br>Print Job starting...", type: 'success', timeout: 3000});
        }, 1500);
      }
    }, this))
    .fail(_.bind(function(xhr) {
      var error = xhr.responseText;
      noty({text: error ? error : "There was an error ejecting drive", timeout: 3000});
    }, this))
    .always(_.bind(function(){
      this.fileView.$('button.copy').removeClass('hide')
      this.fileView.$('button.print').removeClass('hide')
      this.fileView = null;
      this.fileListView = null;
      loadingBtn.removeClass('loading');
      this.$el.foundation('reveal', 'close');
    },this));
  },
  onNoClicked: function(e)
  {
    if(e) e.preventDefault();

    this.$el.foundation('reveal', 'close');

    this.fileView.$('button.copy').removeClass('hide')
    this.fileView.$('button.print').removeClass('hide')
    this.fileView.startPrint();
  },
  onClose: function()
  {
    this.undelegateEvents();
    this.$('.dlg-content').empty();
    this.drive = null;
  }
});

var BrowsingFileView = Backbone.View.extend({
  template: _.template( $("#browsing-file-template").html() ),
  file: null,
  parentView: null,
  events: {
    'click div.exploreFolder': 'exploreFolder',
    'click button.eject': 'eject'
  },
  initialize: function(data)
  {
    this.parentView = data.parentView;

    data.file.set('location', data.file.get('name'));

    var path = data.file.get('name');
    data.file.set('name', path.substr(path.lastIndexOf('/')+1));

    this.file = data.file;
  },
  slideName: function () {
    if (!this.$(".div-container").size() || this.$(".div-container").width()<=0) {
      setTimeout(_.bind(this.slideName,this), 500); // give everything some time to render
    } else {
      if(this.$('.text').width() >= this.$('.div-container').width()){
        this.$('.text').addClass('slide-text')
      } else {
        this.$('.text').removeClass('slide-text')
      }
    }
  },
  render: function()
  {
    var print_file = this.file.toJSON();

    this.downloadProgress = null;
    this.$el.html(this.template({
      p: print_file
    }));

    this.slideName();
    this.delegateEvents();
  },
  eject: function(evt)
  {
    if (evt) evt.preventDefault();

    this.$('button.eject').addClass('hide');
    this.$('.loading-button.eject').addClass('loading');

    $.ajax({
      url: '/api/files/eject',
      type: "POST",
      dataType: "json",
      data:
        {
          drive: this.file.get('location')
        }
    })
    .done(_.bind(function(data) {
      this.$('.loading-button.eject').removeClass('loading');
      if(data.error){
        var error = data.error
        noty({text: "There was an error ejecting drive" + (error ? ': ' + error : ""), timeout: 3000});
        this.$('button.eject').removeClass('hide');
      } else {
        setTimeout(_.bind(function(){
          noty({text: "Drive ejected. You can safely remove the external drive", type: 'success', timeout: 3000});
          this.parentView.render()
      }, this), 1500)
      }
    }, this))
    .fail(_.bind(function(xhr) {
      var error = xhr.responseText;
      noty({text: error ? error : "There was an error ejecting drive", timeout: 3000});
      this.$('.loading-button.eject').removeClass('loading');
      this.$('button.eject').removeClass('hide');
      this.parentView.refresh()
    }, this));
  },
  exploreFolder: function (evt)
  {
    if (evt) evt.preventDefault();

    var filename = this.file.get('location');

    this.parentView.storage_control_view.selected = 'USB';
    this.parentView.storage_control_view.composeLocation(filename);
    this.parentView.externalDrivesRefresh();
  }
});

var BackFolderView = BrowsingFileView.extend({
  template: _.template( $("#back-folder-template").html() ),
  event: {
    'click div.exploreFolder': 'exploreFolder'
  },
  initialize: function(data)
  {
    this.parentView = data.parentView;
  },
  render: function()
  {
    var print_file = {
      name: 'back',
      icon: 'folder'
    }

    this.downloadProgress = null;
    this.$el.html(this.template({
      p: print_file
    }));

    this.delegateEvents();
  },
  exploreFolder: function (evt)
  {
    if (evt) evt.preventDefault();

    this.parentView.storage_control_view.selected = 'USB';
    this.parentView.storage_control_view.composeLocation('back');
    this.parentView.externalDrivesRefresh();
  }
});
