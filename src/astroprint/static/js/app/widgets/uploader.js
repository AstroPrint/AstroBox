var FileUploadBase = Backbone.View.extend({
  events: {
    'fileuploadadd': 'onFileAdded',
    'fileuploadsubmit': 'onFileSubmit',
    'fileuploadprogress': 'onUploadProgress',
    'fileuploadfail': 'onUploadFail',
    'fileuploadalways': 'onUploadAlways',
    'fileuploaddone': 'onUploadDone'
  },
  acceptFileTypes: null,
  signatureUrl: null,
  signatureData: {},
  uploadUrl: null,
  uploadData: {},
  initialize: function(options)
  {
    this.$el.fileupload({
      dropZone: options.dropZone ? options.dropZone : this.$el
    });
  },
  beforeSubmit: function(e, data)
  {
    if (this.signatureUrl) {
      this.progress(1.0);

      var params = this.signatureData;
      _.extend(params, {
        file: data.files[0].name
      });

      var queryStr = [];
      _.each(params, function(v, k) {
        queryStr.push(k+'='+encodeURIComponent(v));
      });

      $.getJSON(this.signatureUrl+'?'+queryStr.join('&'), _.bind(function(response) {
        if (response.url && response.params) {
          data.formData = response.params;
          data.url = response.url;
          data.redirect = response.redirect;
          this.progress(2.0);
          $(e.currentTarget).fileupload('send', data);
        } else {
          this.failed(response.error);
          this.always();
        }
      }, this)).fail(_.bind(function(xhr){
        this.failed("http_error_"+xhr.status);
        this.always();
      }, this));
    } else {
      this.progress(1.0);
      $(e.currentTarget).fileupload('send', data);
    }

    return false;
  },
  onFileAdded: function(e, data)
  {
    if (!this.acceptFileTypes) {
      console.error('acceptFileTypes not set');
      return;
    }

    var uploadErrors = [];
    var acceptFileTypes = this.acceptFileTypes;
    if(data.originalFiles[0]['name'].length && !acceptFileTypes.test(data.originalFiles[0]['name'])) {
      uploadErrors.push('Not a valid file');
    }
    if(uploadErrors.length > 0) {
      this.failed("There was an error uploading: " + uploadErrors.join("<br/>"));
      this.always();
      return false;
    } else {
      return true;
    }
  },
  onFileSubmit: function(e, data)
  {
    if (data.files.length) {
      this.started(data);
      this.progress(0);

      if (!this.signatureUrl) {
        data.url = this.uploadUrl;
        data.formData = this.uploadData;
      }

      if (this.beforeSubmit(e, data)) {
        $(e.currentTarget).fileupload('send', data);
      }
    }

    return false;
  },
  onUploadProgress: function(e, data)
  {
    this.progress(Math.max((data.loaded / data.total * 100.0) * 0.95, 2.0));
  },
  onUploadFail: function(e, data)
  {
    this.failed(data.jqXHR.responseText ? data.jqXHR.responseText : null);
  },
  onUploadAlways: function(e, data)
  {
    this.always();
  },
  onUploadDone: function(e, data)
  {
    this.success(data);
  },
  //Override these
  started: function(data){},
  progress: function(progress){},
  failed: function(error){},
  success: function(fileInfo){},
  always: function(){}
});

var FileUploadCombined = FileUploadBase.extend({
  fileTypes: {
    design: ['stl'],
    print: ['x3g', 'gcode', 'gco']
  },
  currentFileType: null,
  designWarningDlg: null,
  initialize: function(options)
  {
    FileUploadBase.prototype.initialize.call(this, options);

    this.refreshAccept();
  },
  refreshAccept: function()
  {
    if (app.printerProfile.get('driver') == 's3g') {
      this.$el.attr('accept', '.stl, .x3g');
      this.acceptFileTypes = /(\.|\/)(stl|x3g)$/i;
    } else {
      this.$el.attr('accept', '.stl, .gcode, .gco');
      this.acceptFileTypes = /(\.|\/)(stl|gcode|gco)$/i;
    }
  },
  onFileAdded: function(e, data)
  {
    if (FileUploadBase.prototype.onFileAdded.call(this, e, data)) {
      var fileName = data.files[0].name;
      var fileExt = fileName.substr( (fileName.lastIndexOf('.') +1) ).toLowerCase();

      //Let's find out what type of file this is
      this.currentFileType = _.findKey(this.fileTypes, function(v, k) {
        return (_.find(v, function(ext) {
          return ext == fileExt;
        }) != undefined);
      });

      if (this.currentFileType == 'design') {
        if (!this.designWarningDlg) {
          this.designWarningDlg = new DesignUploadWarningDialog();
        }

        this.designWarningDlg.show().then(function(procceed){
          if (procceed) {
            data.submit();
          }
        });

        return false;
      }

      return true;
    } else {
      return false;
    }
  },
  started: function(data)
  {
    if (data.files && data.files.length > 0) {
      var fileName = data.files[0].name;
      var fileExt = fileName.substr( (fileName.lastIndexOf('.') +1) ).toLowerCase();

      if (this.currentFileType == undefined) {
        this.currentFileType = null;
        this.failed('File Type ['+fileExt+'] not supported');
        return;
      }

      switch (this.currentFileType) {
        case 'design':
          this.uploadUrl = null;
          this.signatureUrl = '/api/astroprint/upload-data';
          this.signatureData = {
            file : fileName
          };
        break;

        case 'print':
          this.signatureUrl = null;
          this.signatureData = {};
          this.uploadUrl = '/api/files/local';
        break;
      }
    }
  },
  success: function(data)
  {
    switch(this.currentFileType) {
      case 'design':
        this.progress(98);
        if (data.redirect) {
          window.location.href = data.redirect;
        } else {
          this.failed('Missing redirect url');
        }
      break;

      case 'print':
        this.progress(98);

        var hasFilesView = app.router.loadFilesView(false);

        if ( hasFilesView === true) {
          var promise = app.router.filesView.refreshPrintFiles()
        } else {
          var promise = hasFilesView; //in this case it returns a promise
        }

        promise
          .done(_.bind(function(){
            noty({text: "File uploaded successfully :)", type: 'success', timeout: 3000});
            this.progress(100);
            app.router.filesView.printFilesListView.storage_control_view.selectStorage('local');
            app.router.filesView.fileInfoByName(data.result.files.local.name);
            this.onPrintFileUploaded();
          }, this))
          .fail(_.bind(function(err){
            this.failed(err);
          }, this));

      break;
    }
  },
  failed: function(error)
  {
    this.onError(this.currentFileType, error);
  },

  //Override These
  onPrintFileUploaded: function() {},
  onError: function(type, error) {}
});

var DesignUploadWarningDialog = Backbone.View.extend({
  el: '<div class="reveal-modal medium radius" data-reveal></div>',
  template: _.template($('#design-upload-warning-modal-template').html()),
  promise: null,
  events: {
    'close.fndtn.reveal': 'onModalClose',
    'click button.login': 'onLoginClicked',
    'click button.cancel': 'onCancelClicked',
    'click button.continue': 'onContinueClicked',
  },
  initialize: function()
  {
    this.$el.html( this.template({logged_user: LOGGED_USER}) );
  },
  show: function()
  {
    this.$el.foundation('reveal', 'open');
    this.promise = $.Deferred();
    return this.promise;
  },
  onModalClose: function(e)
  {
    if (this.promise.state() == 'pending') {
      this.promise.resolve(false);
    }

    this.promise = null;
  },
  onLoginClicked: function(e)
  {
    this.promise.resolve(false);
    $('#login-modal').foundation('reveal', 'open');
  },
  onCancelClicked: function(e)
  {
    this.$el.foundation('reveal', 'close');
  },
  onContinueClicked: function(e)
  {
    this.promise.resolve(true);
    this.$el.foundation('reveal', 'close');
  }
})
