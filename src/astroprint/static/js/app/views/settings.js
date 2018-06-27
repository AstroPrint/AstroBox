/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

var SettingsPage = Backbone.View.extend({
  parent: null,
  initialize: function(params) {
    this.parent = params.parent;
  },
  show: function() {
    this.parent.$el.find('.settings-page').addClass('hide');
    this.$el.removeClass('hide');
  }
});

/***********************
* Printer - Connection
************************/

var PrinterConnectionView = SettingsPage.extend({
  el: '#printer-connection',
  template: null,
  settings: null,
  events: {
    'change #settings-baudrate': 'onReconnectClicked',
    'change #settings-serial-port': 'onReconnectClicked',
    'click a.retry-ports': 'retryPortsClicked',
    'click .loading-button.connect button': 'onConnectClicked',
    'click .loading-button.disconnect button': 'onDisconnectClicked',
    'click .loading-button.reconnect button': 'onReconnectClicked',
  },
  initialize: function(params)
  {
    this.listenTo(app.socketData, 'change:printer', this.printerStatusChanged );
    SettingsPage.prototype.initialize.call(this, params);
  },
  show: function() {
    //Call Super
    SettingsPage.prototype.show.apply(this);

    if (!this.settings) {
      this.getInfo();
    } else {
      this.render();
    }
  },
  getInfo: function()
  {
    this.$('a.retry-ports i').addClass('animate-spin');
    $.getJSON(API_BASEURL + 'settings/printer', null, _.bind(function(data) {
      if (data.serial) {
        this.settings = data;
        this.render(); // This removes the animate-spin from the link
      } else {
        noty({text: "No serial settings found.", timeout: 3000});
      }
    }, this))
    .fail(function() {
      noty({text: "There was an error getting serial settings.", timeout: 3000});
      this.$('a.retry-ports i').removeClass('animate-spin');
    })
  },
  render: function()
  {
    if (!this.template) {
      this.template = _.template( $("#printer-connection-settings-page-template").html() );
    }

    this.$('form').html(this.template({
      settings: this.settings
    }));

    this.printerStatusChanged(app.socketData, app.socketData.get('printer'));
    //this.delegateEvents(this.events);
  },
  retryPortsClicked: function(e)
  {
    e.preventDefault();
    this.getInfo();
  },
  sendConnect: function(command_data) {
    var connectionData = {};

    _.each(this.$('form').serializeArray(), function(e){
      connectionData[e.name] = e.value;
    });

    if (connectionData.port) {
      if (app.socketData.get('printer').status != 'connected') {
        this.setViewStatus('connecting')
      } else {
        this.setViewStatus(app.socketData.get('printer').status)
      }

      $.ajax({
        url: API_BASEURL + "connection",
        type: "POST",
        dataType: "json",
        contentType: "application/json; charset=UTF-8",
        data: JSON.stringify(_.extend(connectionData, command_data))
      })
      .fail(_.bind(function(){
        noty({text: "There was an error connecting.", timeout: 3000});
        this.setViewStatus('failed')
      },this ))
    }
  },
  printerStatusChanged: function(s, value)
  {
    this.setViewStatus(value.status);
  },
  setViewStatus: function(status)
  {
    this.$el.removeClass('connecting failed connected closed').addClass(status);
  },
  onConnectClicked: function(e)
  {
    e.preventDefault();

    this.sendConnect({
      command: "connect",
      autoconnect: true,
      save: true
    });
  },
  onDisconnectClicked: function(e)
  {
    e.preventDefault();

    var loadingBtn = $(e.currentTarget).closest('.loading-button');
    loadingBtn.addClass('loading');

    $.ajax({
      url: API_BASEURL + "connection",
      type: "POST",
      dataType: "json",
      contentType: "application/json; charset=UTF-8",
      data: JSON.stringify({
        command: "disconnect"
      })
    })
    .done(_.bind(function() {
      this.setViewStatus('closed');
    }, this))
    .fail(_.bind(function(){
      noty({text: "There was an error disconnecting.", timeout: 3000});
    },this))
    .always(_.bind(function(){
      loadingBtn.removeClass('loading');
    }, this))
  },
  onReconnectClicked: function(e)
  {
    e.preventDefault();

    this.sendConnect({
      command: "reconnect"
    });
  }
});

/***********************
* Printer - Profile
************************/

var PrinterProfileView = SettingsPage.extend({
  el: '#printer-profile',
  template: null,
  settings: null,
  driverChoices: [],
  events: {
    "invalid.fndtn.abide form": 'invalidForm',
    "valid.fndtn.abide form": 'validForm',
    "change input[name='heated_bed']": 'heatedBedChanged',
    "change select[name='driver']": 'driverChanged'
  },
  show: function() {
    SettingsPage.prototype.show.apply(this);

    if (!this.settings) {
      this.settings = app.printerProfile;
      this.getInfo();
    } else {
      this.render();
    }
  },
  getInfo: function()
  {
    $.getJSON(API_BASEURL + 'printer-profile', null, _.bind(function(data) {
      if (data) {
        this.driverChoices = data.driverChoices;
        delete data.driverChoices;
        this.settings.set(data.profile);
        this.render(); // This removes the animate-spin from the link
      } else {
        noty({text: "No Profile found.", timeout: 3000});
      }
    }, this))
    .fail(function() {
      noty({text: "There was an error getting printer profile.", timeout: 3000});
    })
  },
  render: function() {
    if (!this.template) {
      this.template = _.template( $("#printer-profile-settings-page-template").html() );
    }

    this.$el.html(this.template({
      settings: this.settings.toJSON(),
      driverChoices: this.driverChoices
    }));

    this.$el.foundation('abide');
    this.$('#extruder-count').val(this.settings.get('extruder_count'));
  },
  heatedBedChanged: function(e)
  {
    var target = $(e.currentTarget);
    var wrapper = this.$('.input-wrapper.max_bed_temp');

    if (target.is(':checked')) {
      wrapper.removeClass('hide');
    } else {
      wrapper.addClass('hide');
    }
  },
  driverChanged: function(e)
  {
    var target = $(e.currentTarget);
    var wrapper = this.$('.input-wrapper.cancel-gcode');

    this.settings.set('driver', target.val());
    this.render();
  },
  invalidForm: function(e)
  {
    if (e.namespace !== 'abide.fndtn') {
      return;
    }

    noty({text: "Please check your errors", timeout: 3000});
  },
  validForm: function(e) {
    if (e.namespace !== 'abide.fndtn') {
      return;
    }

    var form = this.$('form');
    var loadingBtn = form.find('.loading-button');
    var attrs = {};

    loadingBtn.addClass('loading');

    form.find('input, select, textarea').each(function(idx, elem) {
      var value = null;
      var elem = $(elem);

      if (elem.is('input[type="radio"], input[type="checkbox"]')) {
        value = elem.is(':checked');
      } else {
        value = elem.val();
      }

      attrs[elem.attr('name')] = value;
    });
    attrs.cancel_gcode = attrs.cancel_gcode.trim().split('\n');
    this.settings.save(attrs, {
      patch: true,
      success: _.bind(function() {
        noty({text: "Profile changes saved", timeout: 3000, type:"success"});
        loadingBtn.removeClass('loading');
        //Make sure we reload next time we load this tab
        this.parent.subviews['printer-connection'].settings = null;
      }, this),
      error: function() {
        noty({text: "Failed to save printer profile changes", timeout: 3000});
        loadingBtn.removeClass('loading');
      }
    });
  }
});

/***********************
* Printer - Temperature Presets
************************/

var TemperaturePresetsView = SettingsPage.extend({
  el: '#temperature-presets',
  template: _.template( $("#temperature-presets-settings-page-template").html() ),
  settings: null,
  presetDeleteDlg : null,
  editPresetDialog : null,
  events: {
  'click .stored-presets .delete-preset': 'onDeletePresetClicked',
  'click .new-preset' : "newPresetClicked",
  'click .edit-preset' : "editPresetClicked"
  },
  show: function() {
    SettingsPage.prototype.show.apply(this);
    if (!this.settings) {
      this.settings = app.printerProfile;
      this.getInfo();
    } else {
      this.render();
    }
  },
  getInfo: function()
  {
    $.getJSON(API_BASEURL + 'printer-profile', null, _.bind(function(data) {
      if (data) {
        delete data.driverChoices;
        this.settings.set(data.profile);
        this.render(); // This removes the animate-spin from the link
      } else {
        noty({text: "No Profile found.", timeout: 3000});
      }
    }, this))
    .fail(function() {
      noty({text: "There was an error getting printer profile.", timeout: 3000});
    })
  },
  render: function() {
    this.$el.html(this.template({
      temp_presets: this.settings.attributes.temp_presets,
      heated_bed : this.settings.attributes.heated_bed
    }));

    this.$el.foundation('abide');

  },
  onDeletePresetClicked: function(e)
  {
    e.preventDefault();
    var row = $(e.currentTarget).closest('.row');
    if (!this.presetDeleteDlg){
      this.presetDeleteDlg = new DeleteTemperaturePresetsDialog({parent: this})
    }
    this.presetDeleteDlg.open({
      id: row.data('id'),
      name: row.find('.name').text()
    })
      .done(function(deleted) {
        if (deleted) {
          row.remove();
        }
      })
      .fail(function() {
        noty({text: "Unable to Delete Stored Network"});
      });
  },
  newPresetClicked: function(e)
  {
    e.preventDefault();
    if (!this.editPresetsDialog){
      this.editPresetsDialog = new EditPresetsDialog({parent: this});
    }
    this.editPresetsDialog.open()
  },
  editPresetClicked: function(e)
  {
    var row = $(e.currentTarget).closest('.row');
    e.preventDefault();
    if (!this.editPresetsDialog){
      this.editPresetsDialog = new EditPresetsDialog({parent: this});
    }
    this.editPresetsDialog.open({
      id: row.data('id'),
    })
  },
  updateTemperaturePresets: function(e)
  {
    this.settings.save(attrs, {
      patch: true,
      success: _.bind(function() {
        if(app.router.filesView && app.router.filesView.printFilesListView){
          app.router.filesView.printFilesListView.onPrinterDriverChanged();
        }
        noty({text: "Profile changes saved", timeout: 3000, type:"success"});
        loadingBtn.removeClass('loading');
        //Make sure we reload next time we load this tab
        this.parent.subviews['printer-connection'].settings = null;
      }, this),
      error: function() {
        noty({text: "Failed to save printer profile changes", timeout: 3000});
        loadingBtn.removeClass('loading');
      }
    });
  }
});

var DeleteTemperaturePresetsDialog = Backbone.View.extend({
  el: '#delete-stored-temperature-preset-modal',
  promise: null,
  id : null,
  events: {
    'click button.secondary': 'doClose',
    'click button.alert': 'doDelete',
    'close': 'onClose'
  },
  initialize: function(params) {
    this.parent = params.parent;
  },
  open: function(info)
  {
    this.promise = $.Deferred();
    this.$('.name').text(info.name);
    this.id = info.id

    this.$el.foundation('reveal', 'open');
    return this.promise;
  },
  onClose: function()
  {
    if (this.promise.state() == 'pending') {
      this.promise.resolve(false);
    }
  },
  doClose: function()
  {
    this.$el.foundation('reveal', 'close');
  },
  doDelete: function(e)
  {
    e.preventDefault()
    var loadingBtn = $(e.currentTarget).closest('.loading-button');
    loadingBtn.addClass('loading');

    for(var i = 0; i < this.parent.settings.attributes.temp_presets.length; i++) {
      var obj = this.parent.settings.attributes.temp_presets[i];
      if(obj.id == this.id) {
        this.parent.settings.attributes.temp_presets.splice(i, 1);
        break
      }
    }
    attr = {}
    attr.temp_presets = this.parent.settings.attributes.temp_presets
    this.parent.settings.save(attr, {
      patch: true,
      success: _.bind(function() {
        noty({text: "Temperature Preset saved", timeout: 3000, type:"success"});
        loadingBtn.removeClass('loading');
        //Make sure we reload next time we load this tab
        this.parent.parent.subviews['printer-connection'].settings = null;
        this.doClose();
      }, this),
      error: function() {
        noty({text: "Failed to delete Temperature Preset", timeout: 3000});
        loadingBtn.removeClass('loading');
        this.doClose();
      }
    });

    if (this.parent.settings.attributes.temp_presets.length > 1){
      this.promise.resolve(true);
    } else {
      this.parent.render();
      this.promise.resolve(false);
    }
  }
});

var EditPresetsDialog = Backbone.View.extend({
  el: '#add-preset-modal',
  template: _.template( $("#temperature-presets-add-modal").html() ),
  preset : null,
  events : {
    "click .cancel-add-preset" : "doClose",
    "valid.fndtn.abide form": 'validForm',
  },
  initialize: function(params) {
    this.parent = params.parent;
  },
  open: function(info) {
    if(info) {
      for(var i = 0; i < this.parent.settings.attributes.temp_presets.length; i++) {
        var obj = this.parent.settings.attributes.temp_presets[i];
        if(obj.id == info.id) {
          this.preset = obj
          break
        }
      }
      this.render();
      $('#temperature-preset-name').val(this.preset.name)
      $('#preset-bed-temp').val(this.preset.bed_temp)
      $('#preset-nozzle-temp').val(this.preset.nozzle_temp)
    } else {
      this.preset = null
      this.render();
    }
    this.promise = $.Deferred();
    this.$el.foundation('reveal', 'open');
    return this.promise;
  },
  doClose: function(e)
  {
    e.preventDefault()
    var form = document.getElementById("preset-form");
    form.reset();
    this.$el.foundation('reveal', 'close');
  },
  render: function() {
    this.$el.html(this.template({
      preset: this.preset,
      bed : this.parent.settings.attributes.heated_bed
    }));

    this.$el.foundation('abide');

  },
  validForm: function(e)
  {
    var form = document.getElementById("preset-form");
    var name = $('#temperature-preset-name').val()
    var bed = $('#preset-bed-temp').val() ?  parseInt($('#preset-bed-temp').val()) : 0
    var nozzle =  parseInt($('#preset-nozzle-temp').val())
    if (!this.preset){
      var temp_preset = { 'name' : name, 'bed_temp': bed , 'nozzle_temp' :nozzle }
      $.post(API_BASEURL + 'temperature-preset', temp_preset, _.bind(function(data) {
        temp_preset.id = data.id
        this.parent.settings.attributes.temp_presets.push(temp_preset)
        form.reset();
        this.parent.render()
        noty({text: "Temperature Preset saved.", timeout: 3000, type:"success"});
        this.$el.foundation('reveal', 'close');
      }, this))
      .fail( _.bind(function(data) {
        noty({text: "There was an error saving temperature preset.", timeout: 3000});
      }));
    } else {
      this.preset.name = name;
      this.preset.bed_temp = bed;
      this.preset.nozzle_temp = nozzle;

      attr = {}
      attr.temp_presets = this.parent.settings.attributes.temp_presets
      this.parent.settings.save(attr, {
        patch: true,
        success: _.bind(function() {
          noty({text: "Temperature Preset modified", timeout: 3000, type:"success"});
          //Make sure we reload next time we load this tab
          this.parent.parent.subviews['printer-connection'].settings = null;
          form.reset();
          this.parent.render();
          this.$el.foundation('reveal', 'close');
        }, this),
        error: function() {
          noty({text: "Failed to modify Temperature Preset", timeout: 3000});
          loadingBtn.removeClass('loading');
        }
      });
    }
  }
});

/*************************
* Network - Network Name
**************************/

var NetworkNameView = SettingsPage.extend({
  el: '#network-name',
  template: _.template( $("#network-name-settings-page-template").html() ),
  events: {
    "invalid.fndtn.abide form": 'invalidForm',
    "valid.fndtn.abide form": 'validForm',
    "keyup #network-name": 'nameChanged'
  },
  show: function() {
    //Call Super
    SettingsPage.prototype.show.apply(this);

    if (!this.settings) {
      $.getJSON(API_BASEURL + 'settings/network/name', null, _.bind(function(data) {
        this.settings = data;
        this.render();
      }, this))
      .fail(function() {
        noty({text: "There was an error getting current network name.", timeout: 3000});
      });
    }
  },
  render: function() {
    this.$el.html(this.template({
      settings: this.settings
    }));

    this.$el.foundation();
    this.delegateEvents(this.events);
  },
  nameChanged: function(e)
  {
    var target = $(e.currentTarget);
    var changedElem = this.$('span.network-name');

    changedElem.text(target.val());
  },
  invalidForm: function(e)
  {
    if (e.namespace !== 'abide.fndtn') {
      return;
    }

    noty({text: "Please check your errors", timeout: 3000});
  },
  validForm: function(e) {
    if (e.namespace !== 'abide.fndtn') {
      return;
    }

    var form = this.$('form');
    var loadingBtn = form.find('.loading-button');
    var attrs = {};

    loadingBtn.addClass('loading');

    form.find('input').each(function(idx, elem) {
      var elem = $(elem);
      attrs[elem.attr('name')] = elem.val();
    });

    $.ajax({
      url: API_BASEURL + 'settings/network/name',
      type: 'POST',
      contentType: 'application/json',
      dataType: 'json',
      data: JSON.stringify(attrs)
    })
      .done(_.bind(function(data) {
        noty({text: "Network name changed. It will be effective after the next reboot.", timeout: 3000, type:"success"});
        //Make sure we reload next time we load this tab
        this.settings = data
        this.render();
        this.parent.subviews['network-name'].settings = null;
      }, this))
      .fail(function() {
        noty({text: "Failed to save network name", timeout: 3000});
      })
      .always(function(){
        loadingBtn.removeClass('loading');
      });
  }
});

/*************************
* Camera - Image/Video
**************************/

var CameraVideoStreamView = SettingsPage.extend({
  el: '#video-stream',
  template: null,
  settings: null,
  settingsSizeDefault: '640x480',
  cameraName: 'No camera plugged',
  events: {
    "submit form": 'onFormSubmit',
    "click #buttonRefresh": "refreshPluggedCamera",
    "change #video-stream-encoding": "changeEncoding",
    "change #video-stream-source": "changeSource"
  },
  show: function(previousCameraName) {

    var form = this.$('form');
    var loadingBtn = form.find('.loading-button');

    //Call Super
    SettingsPage.prototype.show.apply(this);
    if (!this.settings) {

      $.getJSON(API_BASEURL + 'camera/connected')
      .done(_.bind(function(response){

        if(response.isCameraConnected){
          if(this.cameraName != response.cameraName){
            this.cameraName = response.cameraName;
          }

          $.getJSON(API_BASEURL + 'settings/camera', null, _.bind(function(data) {

            if(data.structure){

              this.settings = data;

              $.getJSON(API_BASEURL + 'camera/has-properties')
              .done(_.bind(function(response){
                if(response.hasCameraProperties){

                  $.getJSON(API_BASEURL + 'camera/is-resolution-supported',{ size: data.size })
                  .done(_.bind(function(response){
                    if(response.isResolutionSupported){
                      this.videoSettingsError = null;
                      this.render();
                      /*if(previousCameraName){
                        if(!(previousCameraName === this.cameraName)){
                          this.saveData();
                        }
                      } else {
                        this.refreshPluggedCamera();
                        //this.saveData();
                      }*/
                    } else {
                      //setting default settings
                      this.settings.size = this.settingsSizeDefault;
                      //saving new settings <- default settings
                      $.ajax({
                        url: API_BASEURL + 'settings/camera',
                        type: 'POST',
                        contentType: 'application/json',
                        dataType: 'json',
                        data: JSON.stringify(this.settings)
                      });
                      noty({text: "Lowering your camera input resolution", type: 'warning', timeout: 3000});
                      this.videoSettingsError = null;
                      this.saveData();
                      this.render();
                    }

                  },this))
                  .fail(function() {
                    noty({text: "There was an error reading your camera settings.", timeout: 3000});
                  })
                  .always(_.bind(function(){
                    loadingBtn.removeClass('loading');
                  },this));
                } else {
                  this.videoSettingsError = 'Unable to communicate with your camera. Please, re-connect the camera and try again...';
                  this.render();
                }
              },this))
              .fail(_.bind(function(){
                this.videoSettingsError = 'Unable to communicate with your camera. Please, re-connect the camera and try again...';
                this.render();
              },this))
            } else {//camera plugged is not supported by Astrobox
              //this.cameraName = data.cameraName;
              this.videoSettingsError = 'The camera connected is not supported.<br>The minimal resolution is less than 640x480 (minimal resolution supported).';
              this.render();
            }
          }, this))
          .fail(function() {
            noty({text: "There was an error getting Camera settings.", timeout: 3000});
          });
        } else {
          this.videoSettingsError = null;
          this.cameraName = null;
          this.render();
        }
      },this));
    } else {
      this.render();
    }
  },
  changeSource: function(e){
    if(this.$('#video-stream-source option:selected').val() == 'raspicam'){
      this.$('#video-stream-encoding').prop('value', 'h264');
      this.$('#video-stream-encoding').prop('disabled', 'disabled');
      this.onFormSubmit();
    } else {
      this.$('#video-stream-encoding').prop('disabled', '');
    }
  },
  changeEncoding: function(e){

    if(!this.settings){

      var formatSelected = $('#video-stream-format option:selected').val();

      $.ajax({
        url: API_BASEURL + 'settings/camera',
        type: 'POST',
        contentType: 'application/json',
        dataType: 'json',
        data: JSON.stringify({format:formatSelected})
      })
      .done(_.bind(function(data){
        this.settings = data;
      },this));
    }
  },
  refreshPluggedCamera: function(){
    //var previousCameraName = this.cameraName;
    var button = this.$('#buttonRefresh').addClass('loading');

    $.post(API_BASEURL + 'camera/refresh-plugged')
      .done(_.bind(function(response){

        if(response.isCameraPlugged){
          this.settings = null;
          this.cameraName = '';
          //this.show(previousCameraName);
          this.show();
        } else {
          this.cameraName = false;
          this.render();
        }
      },this))
      .always(function(){
        button.removeClass('loading');
      })
  },
  render: function() {
    if (!this.template) {
      this.template = _.template( $("#video-stream-settings-page-template").html() );
    }

    this.$el.html(this.template({
      settings: this.settings
    }));

    this.$el.foundation();

    this.delegateEvents(this.events);

    if(this.$('#video-stream-source option:selected').val() == 'raspicam'){
      this.$('#video-stream-encoding').prop('value', 'h264');
      this.$('#video-stream-encoding').prop('disabled', 'disabled');
    } else {
      this.$('#video-stream-encoding').prop('disabled', '');
    }
  },
  onFormSubmit: function(e) {
      e.preventDefault();
      this.saveData();
    return false;
  },
  saveData: function()
  {
    var form = this.$('form');
    var loadingBtn = form.find('.loading-button');
    var attrs = {};

    loadingBtn.addClass('loading');

    form.find('input, select, textarea').each(function(idx, elem) {
      var value = null;
      var elem = $(elem);

      if (elem.is('input[type="radio"], input[type="checkbox"]')) {
        value = elem.is(':checked');
      } else {
        value = elem.val();
      }

      attrs[elem.attr('name')] = value;
    });

    $.getJSON(API_BASEURL + 'camera/is-resolution-supported',{ size: attrs.size })
    .done(_.bind(function(response){
      if(response.isResolutionSupported){
        $.ajax({
          url: API_BASEURL + 'settings/camera',
          type: 'POST',
          contentType: 'application/json',
          dataType: 'json',
          data: JSON.stringify(attrs)
        })
        .done(_.bind(function(data){
          this.settings = data;
          noty({text: "Camera changes saved", timeout: 3000, type:"success"});
          //Make sure we reload next time we load this tab
          //this.render();
          this.parent.subviews['video-stream'].settings = null;
        },this))
        .fail(function(){
          noty({text: "There was a problem saving camera settings", timeout: 3000});
        })
        .always(_.bind(function(){
          loadingBtn.removeClass('loading');
        },this));
      } else {
        noty({text: "The resolution is not supported by your camera", timeout: 3000});
      }
    },this))
    .fail(function(){
      noty({text: "There was a problem saving camera settings", timeout: 3000});
    })
    .always(_.bind(function(){
      loadingBtn.removeClass('loading');
    },this));
  }
});

/*************************
* Network - Connection
**************************/

var InternetConnectionView = SettingsPage.extend({
  el: '#internet-connection',
  template: null,
  networksDlg: null,
  storedWifiDeleteDlg: null,
  settings: null,
  events: {
    'click .loading-button.list-networks button': 'listNetworksClicked',
    'click .stored-wifis .row .action': 'onDeleteNetworkClicked'
  },
  initialize: function(params) {
    SettingsPage.prototype.initialize.apply(this, arguments);

    this.networksDlg = new WiFiNetworksDialog({parent: this});
    this.storedWifiDeleteDlg = new DeleteWifiNetworkDialog();
  },
  show: function() {
    //Call Super
    SettingsPage.prototype.show.apply(this);

    if (!this.template) {
      this.template = _.template( $("#internet-connection-settings-page-template").html() )
    }
    this.reloadData();
  },
  reloadData: function()
  {
    if (!this.settings) {
      $.getJSON(API_BASEURL + 'settings/network', null, _.bind(function(data) {
        this.settings = data;
        this.render();
      }, this))
      .fail(function() {
        noty({text: "There was an error getting WiFi settings.", timeout: 3000});
      });
    }
  },
  render: function()
  {
    this.$el.html(this.template({
      settings: this.settings
    }));
  },
  connect: function(id, password) {
    var promise = $.Deferred();

    $.ajax({
      url: API_BASEURL + 'settings/network/active',
      type: 'POST',
      contentType: 'application/json',
      dataType: 'json',
      data: JSON.stringify({id: id, password: password})
    })
      .done(_.bind(function(data) {
        if (data.name) {
          var connectionCb = null;

          //Start Timeout
          var connectionTimeout = setTimeout(function(){
            connectionCb.call(this, {status: 'failed', reason: 'timeout'});
          }, 70000); //1 minute

          connectionCb = function(connectionInfo){
            switch (connectionInfo.status) {
              case 'disconnected':
              case 'connecting':
                //Do nothing. the failed case should report the error
              break;

              case 'connected':
                app.eventManager.off('astrobox:InternetConnectingStatus', connectionCb, this);
                noty({text: "Your "+PRODUCT_NAME+" is now connected to "+data.name+".", type: "success", timeout: 3000});
                data.ip = connectionInfo.info.ip
                this.settings.networks['wireless'] = data;
                this.render();
                promise.resolve();
                clearTimeout(connectionTimeout);
              break;

              case 'failed':
                app.eventManager.off('astrobox:InternetConnectingStatus', connectionCb, this);
                if (connectionInfo.reason == 'no_secrets') {
                  message = "Invalid password for "+data.name+".";
                } else {
                  message = "Unable to connect to "+data.name+".";
                }
                promise.reject(message);
                clearTimeout(connectionTimeout);
                break;

              default:
                app.eventManager.off('astrobox:InternetConnectingStatus', connectionCb, this);
                promise.reject("Unable to connect to "+data.name+".");
                clearTimeout(connectionTimeout);
            }
          };

          app.eventManager.on('astrobox:InternetConnectingStatus', connectionCb, this);

        } else if (data.message) {
          promise.reject(data.message)
        }
      }, this))
      .fail(_.bind(function(){
        promise.reject("There was an error selecting WiFi.");
      }, this));

    return promise;
  },
  listNetworksClicked: function(e)
  {
    var el = $(e.target).closest('.loading-button');

    el.addClass('loading');

    $.getJSON(
      API_BASEURL + "settings/network/wifi-networks",
      _.bind(function(data) {
        if (data.message) {
          noty({text: data.message});
        } else if (data.networks) {
          var self = this;
          this.networksDlg.open(_.sortBy(_.uniq(_.sortBy(data.networks, function(el){return el.name}), true, function(el){return el.name}), function(el){
            el.active = self.settings.networks.wireless && self.settings.networks.wireless.name == el.name;
            return -el.signal
          }));
        }
      }, this)
    ).
    fail(function(){
      noty({text: "There was an error retrieving networks.", timeout:3000});
    }).
    complete(function(){
      el.removeClass('loading');
    });
  },
  onDeleteNetworkClicked: function(e)
  {
    e.preventDefault();
    var row = $(e.currentTarget).closest('.row');

    this.storedWifiDeleteDlg.open({
      id: row.data('id'),
      name: row.find('.name').text(),
      active: row.hasClass('active')
    })
      .done(_.bind(function(deleted) {
        if (deleted) {
          row.remove();
          this.settings = null;
          this.reloadData();
        }
      }, this))
      .fail(function() {
        noty({text: "Unable to Delete Stored Network"});
      });
  }
});

var DeleteWifiNetworkDialog = Backbone.View.extend({
  el: '#delete-stored-wifi-modal',
  networkId: null,
  promise: null,
  events: {
    'click button.secondary': 'doClose',
    'click button.alert': 'doDelete',
    'close': 'onClose'
  },
  open: function(info)
  {
    this.promise = $.Deferred();
    this.networkId = info.id;
    this.$('.name').text(info.name);

    if (info.active) {
      this.$el.addClass('active');
    } else {
      this.$el.removeClass('active');
    }

    this.$el.foundation('reveal', 'open');
    return this.promise;
  },
  onClose: function()
  {
    if (this.promise.state() == 'pending') {
      this.promise.resolve(false);
    }
  },
  doClose: function()
  {
    this.$el.foundation('reveal', 'close');
  },
  doDelete: function(e)
  {
    e.preventDefault()

    var loadingBtn = $(e.currentTarget).closest('.loading-button');

    loadingBtn.addClass('loading');

    $.ajax({
      url: API_BASEURL + "settings/network/stored-wifi/" + this.networkId,
      type: "DELETE",
    })
      .done(_.bind(function(){
        this.promise.resolve(true);
      }, this))
      .fail(_.bind(function(){
        this.promise.reject();
      }, this))
      .always(_.bind(function() {
        loadingBtn.removeClass('loading');
        this.doClose();
      },this));
  }
});

var WiFiNetworkPasswordDialog = Backbone.View.extend({
  el: '#wifi-network-password-modal',
  events: {
    'click button.connect': 'connectClicked',
    'submit form': 'connect',
    'change #show-password': 'onShowPasswordChanged'
  },
  template: _.template($('#wifi-network-password-modal-template').html()),
  parent: null,
  initialize: function(params)
  {
    this.parent = params.parent;
  },
  render: function(wifiInfo)
  {
    this.$el.html( this.template({wifi: wifiInfo}) );
  },
  open: function(wifiInfo)
  {
    this.render(wifiInfo);
    this.$el.foundation('reveal', 'open', {
      close_on_background_click: false,
      close_on_esc: false
    });
    this.$el.one('opened', _.bind(function() {
      this.$el.find('.network-password-field').focus();
    }, this));
  },
  connectClicked: function(e)
  {
    e.preventDefault();

    var form = this.$('form');
    form.submit();
  },
  onShowPasswordChanged: function(e)
  {
    var target = $(e.currentTarget);
    var checked = target.is(':checked');
    var field = this.$('input[name=password]');

    if (checked) {
      field.attr('type', 'text');
    } else {
      field.attr('type', 'password');
    }
  },
  connect: function(e)
  {
    e.preventDefault()
    var form = $(e.currentTarget);

    var id = form.find('.network-id-field').val();
    var password = form.find('.network-password-field').val();
    var loadingBtn = this.$('button.connect').closest('.loading-button');
    var cancelBtn = this.$('button.cancel');

    loadingBtn.addClass('loading');
    cancelBtn.hide();

    this.parent.connect(id, password)
      .done(_.bind(function(){
        form.find('.network-password-field').val('');
        this.$el.foundation('reveal', 'close');
        loadingBtn.removeClass('loading');
        cancelBtn.show();
      }, this))
      .fail(_.bind(function(message){
        loadingBtn.removeClass('loading');
        cancelBtn.show();
        noty({text: message, timeout: 3000});
        this.$el.foundation('reveal', 'close');
      }, this));

    return false;
  }
});

var WiFiNetworksDialog = Backbone.View.extend({
  el: '#wifi-network-list-modal',
  networksTemplate: _.template( $("#wifi-network-modal-row").html() ),
  passwordDlg: null,
  parent: null,
  networks: null,
  initialize: function(params) {
    this.parent = params.parent;
  },
  open: function(networks) {
    var content = this.$el.find('.modal-content');
    content.empty();

    this.networks = networks;

    content.html(this.networksTemplate({
      networks: this.networks
    }));

    content.find('button').bind('click', _.bind(this.networkSelected, this));

    this.$el.foundation('reveal', 'open');
  },
  networkSelected: function(e) {
    e.preventDefault();

    var button = $(e.target);

    if (!this.passwordDlg) {
      this.passwordDlg = new WiFiNetworkPasswordDialog({parent: this.parent});
    }

    var network = this.networks[button.data('id')]

    if (network.secured) {
      this.passwordDlg.open(network);
    } else {
      var loadingBtn = button.closest('.loading-button');

      loadingBtn.addClass('loading');

      this.parent.connect(network.id, null)
        .done(_.bind(function(){
          this.$el.foundation('reveal', 'close');
          loadingBtn.removeClass('loading');
        }, this))
        .fail(function(message){
          noty({text: message, timeout: 3000});
          loadingBtn.removeClass('loading');
        });
    }
  }
});

/*************************
* Network - Wifi Hotspot
**************************/

var WifiHotspotView = SettingsPage.extend({
  el: '#wifi-hotspot',
  template: _.template( $("#wifi-hotspot-settings-page-template").html() ),
  settings: null,
  events: {
    'click .loading-button.start-hotspot button': 'startHotspotClicked',
    'click .loading-button.stop-hotspot button': 'stopHotspotClicked',
    'change .hotspot-off input': 'hotspotOffChanged'
  },
  show: function() {
    //Call Super
    SettingsPage.prototype.show.apply(this);

    if (!this.settings) {
      $.getJSON(API_BASEURL + 'settings/network/hotspot', null, _.bind(function(data) {
        this.settings = data;
        this.render();
      }, this))
      .fail(function() {
        noty({text: "There was an error getting WiFi Hotspot settings.", timeout: 3000});
      });
    }
  },
  render: function() {
    this.$el.html(this.template({
      settings: this.settings
    }));
  },
  startHotspotClicked: function(e) {
    var el = $(e.target).closest('.loading-button');

    el.addClass('loading');

    $.ajax({
      url: API_BASEURL + "settings/network/hotspot",
      type: "POST",
      success: _.bind(function(data, code, xhr) {
        noty({text: 'Your '+PRODUCT_NAME+' has created a hotspot. Connect to <b>'+this.settings.hotspot.name+'</b>.', type: 'success', timeout:3000});
        this.settings.hotspot.active = true;
        this.render();
      }, this),
      error: function(xhr) {
        noty({text: xhr.responseText, timeout:3000});
      },
      complete: function() {
        el.removeClass('loading');
      }
    });
  },
  stopHotspotClicked: function(e) {
    var el = $(e.target).closest('.loading-button');

    el.addClass('loading');

    $.ajax({
      url: API_BASEURL + "settings/network/hotspot",
      type: "DELETE",
      success: _.bind(function(data, code, xhr) {
        noty({text: 'The hotspot has been stopped', type: 'success', timeout:3000});
        this.settings.hotspot.active = false;
        this.render();
      }, this),
      error: function(xhr) {
        noty({text: xhr.responseText, timeout:3000});
      },
      complete: function() {
        el.removeClass('loading');
      }
    });
  },
  hotspotOffChanged: function(e)
  {
    var target = $(e.currentTarget);
    var checked = target.is(':checked');

    $.ajax({
      url: '/api/settings/network/hotspot',
      method: 'PUT',
      data: JSON.stringify({
        'hotspotOnlyOffline': checked
      }),
      contentType: 'application/json',
      dataType: 'json'
    })
      .done(_.bind(function(){
        this.settings.hotspot.hotspotOnlyOffline = checked;
      }, this))
      .fail(function(){
        noty({text: "There was an error saving hotspot option.", timeout: 3000});
      });
  }
});

/********************
* Software - Plugins
*********************/

var SoftwarePluginsView = SettingsPage.extend({
  el: '#software-plugins',
  template: null,
  events: {
    "click .installed .row a.delete-link": "onRemoveClicked"
  },
  pluginsInfo: null,
  uploader: null,
  template: null,
  deleteDlg: null,
  initialize: function(opts)
  {
    SettingsPage.prototype.initialize.apply(this, arguments);
    this.uploader = new PluginUploader({
      el: this.$('input.file-upload'),
      progressBar: this.$('.upload-progress'),
      buttonContainer: this.$('.upload-buttons'),
      installedCallback: _.bind(this.onPluginInstalled,this)
    });
  },
  show: function()
  {
    SettingsPage.prototype.show.apply(this);

    if (!this.template) {
      this.template = _.template( $("#software-plugings-settings-page-template").html() )
    }

    if (!this.pluginsInfo) {
      this.refeshPlugins();
    }
  },
  refeshPlugins: function()
  {
    return $.getJSON(API_BASEURL + 'settings/software/plugins')
      .done( _.bind(function(data){
        this.pluginsInfo = data;
        this.render();
      },this))
      .fail(function(xhr){
        noty({text: "There was an error getting Plugin Information.", timeout: 3000});
        console.error("Request failed with: " + xhr.status);
      })
  },
  render: function()
  {
    this.$('.installed').html(this.template({
      plugins: this.pluginsInfo
    }));
  },
  onPluginInstalled: function(data)
  {
    this.refeshPlugins();

    if (data.definition.services.indexOf("printerComms") >= 0) {
      this.cleanPrinterProfile();
    }
  },
  onRemoveClicked: function(e)
  {
    e.preventDefault();

    if (!this.deleteDlg) {
      this.deleteDlg = new DeletePluginDialog({parent: this});
    }

    var row = $(e.currentTarget).closest('.row');
    this.deleteDlg.open(row.data('plugin-id'), row.data('plugin-name'));
  },
  cleanPrinterProfile: function()
  {
    this.parent.cleanPrinterProfile()
  }
});


var PluginUploader = FileUploadBase.extend({
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
    this.uploadUrl = API_BASEURL + 'settings/software/plugins';
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
        message = 'The file is not a valid plugin';
      break;

      case 'invalid_plugin_file':
        message = 'The plugin file has errors';
      break;

      case 'error_checking_file':
        message = 'There was an error checking the plugin file';
      break;

      case 'invalid_plugin_definition':
        message = 'The plugin definition file is not valid';
      break;

      case 'incompatible_plugin':
        message = 'The API version used by the plugin is not compatible.';

      case 'already_installed':
        message = "The Plugin is already installed. Please remove old version first.";
      break;
    }

    this.onError(message);
  },
  success: function(data)
  {
    if (data.result.tmp_file) {
      $.ajax({
        url: API_BASEURL + 'settings/software/plugins/install',
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
          this.onError('Unable to install plugin');
        }, this))
    } else {
      this.onError('Unable to install plugin');
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

var DeletePluginDialog = Backbone.View.extend({
  el: '#delete-plugin-modal',
  events: {
    'click button.secondary': 'doClose',
    'click button.alert': 'doDelete',
    'open.fndtn.reveal': 'onOpen'
  },
  parent: null,
  id: null,
  name: null,
  initialize: function(options)
  {
    this.parent = options.parent;
  },
  open: function(id, name)
  {
    this.id = id;
    this.name = name;

    this.$('.name').text(name);

    this.$el.foundation('reveal', 'open');
  },
  doClose: function()
  {
    this.$el.foundation('reveal', 'close');
  },
  doDelete: function()
  {
    var loadingBtn = this.$('.loading-button');
    loadingBtn.addClass('loading');

    $.ajax({
      url: API_BASEURL + 'settings/software/plugins',
      type: 'DELETE',
      contentType: 'application/json',
      dataType: 'json',
      data: JSON.stringify({id: this.id})
    })
      .done(_.bind(function(data){
        this.parent.refeshPlugins();
        this.doClose();

        if (data.services.indexOf('printerComms') >= 0) {
          this.parent.cleanPrinterProfile();
        }
      }, this))
      .fail(function(){
        loadingBtn.addClass('failed');
        setTimeout(function(){
          loadingBtn.removeClass('failed');
        }, 3000);
      })
      .always(function(){
        loadingBtn.removeClass('loading');
      });
  }
});

/********************
* Software - License
*********************/

var SoftwareLicenseView = SettingsPage.extend({
  el: '#software-license',
  template: null,
  show: function()
  {
    SettingsPage.prototype.show.apply(this);

    if (!this.template) {
      this.template = _.template( $("#software-license-settings-page-template").html() )
    }

    $.getJSON(API_BASEURL + 'settings/software/license')
      .done(_.bind(function(data){
        this.render(data)
      }, this))
      .fail(function() {
        noty({text: "There was an error getting License Information.", timeout: 3000});
      });
  },
  render: function(data)
  {
    this.$el.html(this.template({
      status: data.is_valid ? 'ok':'nok',
      license: data
    }));

    $.localtime.format(this.$el);
  }
});


/********************
* Software - Update
*********************/

var SoftwareUpdateView = SettingsPage.extend({
  el: '#software-update',
  events: {
    'click .loading-button.check button': 'onCheckClicked'
  },
  systemInfo: null,
  versionsInfo: null,
  outdatedTemplate: null,
  additionalPackageTemplate: null,
  updateDialog: null,
  show: function()
  {
    SettingsPage.prototype.show.apply(this);

    if (!this.systemInfo) {
      $.when(
        $.getJSON(API_BASEURL + 'settings/software/system-info', null),
        $.getJSON(API_BASEURL + 'settings/software/versions', null)
      )
        .done(_.bind(function(systemInfo, versionsInfo) {
          this.systemInfo = systemInfo[0];
          if (systemInfo.outdated) {
            if (!this.outdatedTemplate) {
              this.outdatedTemplate = _.template( $("#software-system-outdated-template").html() );
            }
            //Show the outdated warning
            this.$el.prepend( this.outdatedTemplate( systemInfo ));
          }

          this.versionsInfo = versionsInfo[0];

          var additionalSwContainer = this.$('.additional-sw-container');

          additionalSwContainer.empty().hide();

          if (this.versionsInfo.additional.length > 0) {
            if (!this.additionalPackageTemplate) {
              this.additionalPackageTemplate = _.template( $("#software-additional-software-template").html() );
            }

            additionalSwContainer.html( this.additionalPackageTemplate( {packages: this.versionsInfo.additional} ) ).show();
          }
        }, this))
        .fail(function() {
          noty({text: "There was an error getting System Information.", timeout: 3000});
        });
    }
  },
  onCheckClicked: function(e)
  {
    var loadingBtn = this.$el.find('.loading-button.check');
    loadingBtn.addClass('loading');
    $.ajax({
      url: API_BASEURL + 'settings/software/check',
      type: 'GET',
      dataType: 'json',
      success: _.bind(function(data) {
        if (!this.updateDialog) {
          this.updateDialog = new SoftwareUpdateDialog();
        }

        this.updateDialog.open(data);
      }, this),
      error: function(xhr) {
        if (xhr.status == 400) {
          noty({text: xhr.responseText, timeout: 3000});
        } else {
          noty({text: "There was a problem checking for new software.", timeout: 3000});
        }
      },
      complete: function() {
        loadingBtn.removeClass('loading');
      }
    });
  }
});

var SoftwareUpdateDialog = Backbone.View.extend({
  el: '#software-update-modal',
  data: null,
  contentTemplate: null,
  open: function(data)
  {
    if (!this.contentTemplate) {
      this.contentTemplate = _.template( $("#software-update-modal-content").text() )
    }

    this.data = data;

    var content = this.$el.find('.content');
    content.empty();
    content.html(this.contentTemplate({
      data: data,
      date_format: app.utils.dateFormat
    }));

    content.find('button.cancel').bind('click', _.bind(this.close, this));
    content.find('button.go').bind('click', _.bind(this.doUpdate, this));

    this.$el.foundation('reveal', 'open');
  },
  close: function()
  {
    this.$el.foundation('reveal', 'close');
  },
  doUpdate: function()
  {
    var loadingBtn = this.$el.find('.loading-button');
    loadingBtn.addClass('loading');

    var releasesIds = [];

    _.each(this.data.releases, function(r) {
      if (!r.is_current && r.release) {
        releasesIds.push(r.release.id)
      }
    });

    $.ajax({
      url: API_BASEURL + 'settings/software/update',
      type: 'POST',
      dataType: 'json',
      contentType: 'application/json',
      data: JSON.stringify({
        release_ids: releasesIds
      }),
      success: function() {
        //reset the page to show updating progress
        location.reload();
      },
      error: function(xhr) {
        if (xhr.status == 400) {
          noty({text: xhr.responseText, timeout: 3000});
        } else {
          noty({text: "There was a problem updating to the new version.", timeout: 3000});
        }
        loadingBtn.removeClass('loading');
      }
    });
  }
});

/************************
* Software - Advanced
*************************/

var SoftwareAdvancedView = SettingsPage.extend({
  el: '#software-advanced',
  template: _.template( $("#software-advanced-content-template").html() ),
  resetConfirmDialog: null,
  sendLogDialog: null,
  clearLogDialog: null,
  settings: null,
  events: {
    'change #serial-logs': 'serialLogChanged',
    'change #apikey-regenerate': 'regenerateApiKeyChange',
    'change select.update-channel': 'onUpdateChannelChanged'
  },
  initialize: function(params)
  {
    SettingsPage.prototype.initialize.apply(this, arguments);
    this.resetConfirmDialog = new ResetConfirmDialog();
    this.sendLogDialog = new SendLogDialog();
    this.clearLogDialog = new ClearLogsDialog({parent: this});
  },
  show: function()
  {
    //Call Super
    SettingsPage.prototype.show.apply(this);

    if (!this.settings) {
      $.getJSON(API_BASEURL + 'settings/software/advanced', null, _.bind(function(data) {
        this.settings = data;
        this.render();
      }, this))
      .fail(function() {
        noty({text: "There was an error getting software advanced settings.", timeout: 3000});
      });
    }
  },
  render: function()
  {
    this.$el.html(this.template({
      data: this.settings,
      size_format: app.utils.sizeFormat
    }));

    this.$('select.update-channel').val(this.settings.updateChannel);
  },
  regenerateApiKeyChange: function(e)
  {
    var target = $(e.currentTarget);
    var active = target.is(':checked');

    $.ajax({
      url: '/api/settings/software/advanced/apikey',
      method: 'PUT',
      data: JSON.stringify({
        'regenerate': active
      }),
      contentType: 'application/json',
      dataType: 'json'
    })
    .fail(function(){
      noty({text: "There was an error changing key regeneration.", timeout: 3000});
      target.prop('checked', !active);
    });
  },
  serialLogChanged: function(e)
  {
    var target = $(e.currentTarget);
    var active = target.is(':checked');

    $.ajax({
      url: '/api/settings/software/logs/serial',
      method: 'PUT',
      data: JSON.stringify({
        'active': active
      }),
      contentType: 'application/json',
      dataType: 'json'
    })
    .done(function(){
      if (active) {
        $('#app').addClass('serial-log');
      } else {
        $('#app').removeClass('serial-log');
      }
    })
    .fail(function(){
      noty({text: "There was an error changing serial logs.", timeout: 3000});
      target.prop('checked', !active);
    });
  },
  onUpdateChannelChanged: function(e)
  {
    e.preventDefault();

    var select = $(e.currentTarget);
    var oldValue = this.settings.updateChannel;
    var newValue = select.val();

    $.ajax({
      url: '/api/settings/software/advanced/update-channel',
      method: 'PUT',
      data: JSON.stringify({
        'channel': newValue
      }),
      contentType: 'application/json',
      dataType: 'json'
    })
    .done(_.bind(function(){
      this.settings.updateChannel = newValue;
    }, this))
    .fail(_.bind(function(){
      noty({text: "There was an error changing update channel.", timeout: 3000});
      this.settings.updateChannel = oldValue;
      select.val(oldValue);
    }, this));
  }
});

var SendLogDialog = Backbone.View.extend({
  el: '#send-logs-modal',
  events: {
    'click button.secondary': 'doClose',
    'click button.success': 'doSend',
    'open.fndtn.reveal': 'onOpen'
  },
  onOpen: function()
  {
    this.$('input[name=ticket]').val('');
    this.$('textarea[name=message]').val('');
  },
  doClose: function()
  {
    this.$el.foundation('reveal', 'close');
    this.$('input[name=ticket]').val('');
    this.$('textarea[name=message]').val('');
  },
  doSend: function()
  {
    var button = this.$('.loading-button');

    var data = {
      ticket: this.$('input[name=ticket]').val(),
      message: this.$('textarea[name=message]').val()
    };

    button.addClass('loading');

    $.post(API_BASEURL + 'settings/software/logs', data)
      .done(_.bind(function(){
        noty({text: "Logs sent to AstroPrint!", type: 'success', timeout: 3000});
        this.$el.foundation('reveal', 'close');
        this.$('input[name=ticket]').val('');
        this.$('textarea[name=message]').val('');
      },this))
      .fail(function(){
        noty({text: "There was a problem sending your logs.", timeout: 3000});
      })
      .always(function(){
        button.removeClass('loading');
      });
  }
});

var ClearLogsDialog = Backbone.View.extend({
  el: '#delete-logs-modal',
  events: {
    'click button.secondary': 'doClose',
    'click button.alert': 'doDelete',
    'open.fndtn.reveal': 'onOpen'
  },
  parent: null,
  initialize: function(options)
  {
    this.parent = options.parent;
  },
  doClose: function()
  {
    this.$el.foundation('reveal', 'close');
  },
  doDelete: function()
  {
    this.$('.loading-button').addClass('loading');
    $.ajax({
      url: API_BASEURL + 'settings/software/logs',
      type: 'DELETE',
      contentType: 'application/json',
      dataType: 'json',
      data: JSON.stringify({}),
      success: _.bind(function() {
        this.parent.$('.size').text('0 kB');
        this.doClose()
      }, this),
      error: function(){
        noty({text: "There was a problem clearing your logs.", timeout: 3000});
      },
      complete: _.bind(function() {
        this.$('.loading-button').removeClass('loading');
      }, this)
    })
  }
});

var ResetConfirmDialog = Backbone.View.extend({
  el: '#restore-confirm-modal',
  events: {
    'click button.secondary': 'doClose',
    'click button.alert': 'doReset',
    'open.fndtn.reveal': 'onOpen'
  },
  onOpen: function()
  {
    this.$('input').val('');
  },
  doClose: function()
  {
    this.$el.foundation('reveal', 'close');
  },
  doReset: function()
  {
    if (this.$('input').val() == 'RESET') {
      var loadingBtn = this.$('.loading-button');
      loadingBtn.addClass('loading');

      $.ajax({
        url: API_BASEURL + 'settings/software/settings',
        type: 'DELETE',
        contentType: 'application/json',
        dataType: 'json',
        data: JSON.stringify({})
      })
      .done(function(){
        noty({text: "Device Reset, please wait for reload...", type: 'success', timeout: 7000});
        setTimeout(function(){
          location.href = "";
        }, 7000);
      })
      .fail(function(){
        loadingBtn.removeClass('loading');
        noty({text: "There was a problem with your reset.", timeout: 3000});
      });
    }
  }
});


/******************************************/

var SettingsMenu = Backbone.View.extend({
  el: '#settings-side-bar',
  subviews: null,
  initialize: function(params) {
    if (params.subviews) {
      this.subviews = params.subviews;
    }
  },
  changeActive: function(page) {
    if (!page) {
      //Get the first available
      page = _.find(_.keys(this.subviews), _.bind(function(sv) {
        return this.$('li.'+sv).length > 0;
      }, this));
    }

    var target = this.$('li.'+page);
    this.$('li.active').removeClass('active');
    target.closest('li').addClass('active');
    this.subviews[page].show();
  }
});

var SettingsView = Backbone.View.extend({
  el: '#settings-view',
  menu: null,
  subviews: null,
  initialize: function()
  {
    this.subviews = {
      'printer-connection': new PrinterConnectionView({parent: this}),
      'printer-profile': new PrinterProfileView({parent: this}),
      'temperature-presets': new TemperaturePresetsView({parent: this}),
      'network-name': new NetworkNameView({parent: this}),
      'internet-connection': new InternetConnectionView({parent: this}),
      'video-stream': new CameraVideoStreamView({parent: this}),
      'wifi-hotspot': new WifiHotspotView({parent: this}),
      'software-plugins': new SoftwarePluginsView({parent: this}),
      'software-update': new SoftwareUpdateView({parent: this}),
      'software-advanced': new SoftwareAdvancedView({parent: this}),
      'software-license': new SoftwareLicenseView({parent: this})
    };
    this.menu = new SettingsMenu({subviews: this.subviews});
  },
  onShow: function()
  {
    this.subviews['printer-connection'].show();
  },
  cleanPrinterProfile: function()
  {
    this.subviews['printer-profile'].settings = null;
  }
});
