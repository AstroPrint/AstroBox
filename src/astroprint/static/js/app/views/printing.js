/*
 *  (c) 3DaGoGo, Inc. (product@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */
var PhotoView = CameraViewBase.extend({
  el: "#printing-view .camera-view",
  template: _.template( this.$("#photo-printing-template").html()),
  events: {
    'click button.take-pic': 'onCameraBtnClicked',
    'change .timelapse select': 'timelapseFreqChanged',
    "change #camera-mode-printing": 'cameraModeChanged',
    'click .button-full-screen': 'fullScreenClicked'
  },
  parent: null,
  print_capture: null,
  photoSeq: 0,
  initialize: function(options)
  {
    this.print_capture = app.socketData.get('print_capture');
    this.parent = options.parent;
    this.listenTo(app.socketData, 'change:printing_progress', this.onPrintingProgressChanged);
    this.initCamera();
  },
  onCameraBtnClicked: function(e)
  {
    e.preventDefault();

    var target = $(e.currentTarget);
    var loadingBtn = target.closest('.loading-button');

    $('.icon-3d-object').hide();
    loadingBtn.addClass('loading');

    this.buttonEvent()
      .fail(function(){
        $('.icon-3d-object').show();
        noty({text: "Camera Error.", timeout: 3000});
      })
      .always(function(){
        loadingBtn.removeClass('loading');
      });
  },
  getPhotoContainer: function()
  {
    return this.$('.camera-image');
  },
  getVideoContainer: function()
  {
    return this.$('#video-stream');
  },
  cameraModeChanged: function(e)
  {
    var target = $(e.currentTarget);
    var selectedFreqValue = this.$('#freqSelector').val();

    if(this.cameraMode == 'video'){
      this.stopStreaming();
    }

    this.cameraMode = this.cameraModeByValue(target.is(':checked'));
    this.render();
    this.$('#freqSelector').val(selectedFreqValue);
  },
  manageVideoStreamingEvent: function(value)
  {
    this.onHide();//re-used function
    this.videoStreamingError = value.message;

    if(value.message.indexOf('camera settings have been changed') > -1){
        this.videoStreamingErrorTitle = 'Camera settings changed'
      } else {
        this.videoStreamingErrorTitle = null;
      }

    this.render();
  },
  cameraInitialized: function()
  {
    CameraViewBase.prototype.cameraInitialized.call(this);

    app.eventManager.on('astrobox:videoStreamingEvent', this.manageVideoStreamingEvent, this);

    this.listenTo(app.socketData, 'change:print_capture', this.onPrintCaptureChanged);
    this.listenTo(app.socketData, 'change:camera', this.onCameraChanged);

    this.onCameraChanged(app.socketData, app.socketData.get('camera'));

    this.print_capture = app.socketData.get('print_capture');
  },
  render: function()
  {
    this.$el.html(this.template());

    var imageNode = this.$('.camera-image');
    var imageUrl = null;

    if (this.print_capture && this.print_capture.last_photo) {
      imageUrl = this.print_capture.last_photo;
    } else if (this.parent.printing_progress && this.parent.printing_progress.rendered_image) {
      imageUrl = this.parent.printing_progress.rendered_image;
    }

    if (imageNode.attr('src') != imageUrl) {
      imageNode.attr('src', imageUrl);
    }

    if(!this.canStream){
      //print capture button
      if (this.print_capture && (!this.print_capture.paused || this.print_capture.freq == 'layer')) {
        this.$('.timelapse .dot').addClass('blink-animation');
      } else {
        this.$('.timelapse .dot').removeClass('blink-animation');
      }
    }

    //overaly
    if (this.parent.paused) {
      this.$('.timelapse .overlay').show();
    } else {
      this.$('.timelapse .overlay').hide();
    }

    //select
    var freq = 0;
    if (this.print_capture) {
      freq = this.print_capture.freq;
    }

    this.$('.timelapse select').val(freq);


    //Progress data
    var filenameNode = this.$('.progress .filename');
    var printing_progress = this.parent.printing_progress;
    console.log("....",printing_progress)

    if (filenameNode.text() != printing_progress.printFileName) {
      filenameNode.text(printing_progress.printFileName);
    }

    //progress bar
    this.$el.find('.progress .meter').css('width', printing_progress.percent+'%');
    this.$el.find('.progress .progress-label').text(printing_progress.percent+'%');

    //time
    var time = this._formatTime(printing_progress.time_left);
    this.$el.find('.estimated-hours').text(time[0]);
    this.$el.find('.estimated-minutes').text(time[1]);
    this.$el.find('.estimated-seconds').text(time[2]);

    //layers
    this.$el.find('.current-layer').text(printing_progress.current_layer);
    if (printing_progress.layer_count) {
      this.$el.find('.layer-count').text(printing_progress.layer_count);
    }

  },
  onCameraChanged: function(s, value)
  {
    var cameraControls = this.$('.camera-controls');

    //Camera controls section
    if (value) {
      if (cameraControls.hasClass('hide')) {
        cameraControls.removeClass('hide');
      }
    } else if (!cameraControls.hasClass('hide')) {
      cameraControls.addClass('hide');
    }
  },
  onPrintCaptureChanged: function(s, value)
  {
    this.print_capture = value;
    if (value) {
      if(this.cameraMode == 'photo'){
        if(value && value.last_photo){
           var img = this.$('.camera-image');
           img.attr('src',value.last_photo);
         }
      }
      this.$('.timelapse select').val(value.freq);
    }
  },
  onPrintingProgressChanged: function(s, value)
  {
    var imgCont = this.$('.camera-image');
    var imgSrc = imgCont.attr('src');

    //This allows the change to propagate
    setTimeout(_.bind(function(){
      if (!imgSrc && value) {
        if (this.cameraAvailable) {
          if (this.cameraMode == 'photo') {
            if (value.last_photo) {
              imgCont.attr('src', value.last_photo);
            } else if (value.rendered_image) {
              imgCont.attr('src', value.rendered_image);
            }
          }
        } else if (imgSrc != value.rendered_image) {
          imgCont.attr('src', value.rendered_image);
        }
      }
    }, this), 1);
  },
  refreshPhoto: function(e)
  {
    var loadingBtn = $(e.target).closest('.loading-button');
    var printing_progress = this.parent.printing_progress;

    loadingBtn.addClass('loading');

    if(this.cameraMode == 'photo'){

      var img = this.$('.camera-image');

      img.one('load', function() {
        loadingBtn.removeClass('loading');
      });
      img.one('error', function() {
        loadingBtn.removeClass('loading');
        $(this).attr('src', null);
      });

      img.attr('src', '/camera/snapshot?apikey='+UI_API_KEY+'&text='+encodeURIComponent(text)+'&seq='+this.photoSeq++);
    }
  },
  timelapseFreqChanged: function(e)
  {
    var newFreq = $(e.target).val();

    if (!this.print_capture || newFreq != this.print_capture.freq) {
      $.ajax({
        url: API_BASEURL + "camera/timelapse",
        type: "POST",
        dataType: "json",
        data: {
          freq: newFreq
        }
      }).done ( (data)=> {
      })
      .fail(_.bind(function(data){
        if (data.status == 402){
          this.$(".timelapse").addClass('hide');
          this.$(".locked").removeClass('hide');
          $('#upgrade-plan').foundation('reveal', 'open');
        } else {
          noty({text: "There was an error adjusting your print capture.", timeout: 3000});
        }
      }, this));
    }
  },
  onPrintingHide: function()
  {
    if(this.cameraMode == 'video'){
      this.stopStreaming();
    }
  },
  fullScreenClicked: function(e)
  {
    if ($('.camera-view').hasClass('fullscreen')) {
      $('.camera-view').removeClass('fullscreen');
      $('.info').removeClass('fullscreen');
    } else {
      $('.camera-view').addClass('fullscreen');
      $('.info').addClass('fullscreen');
      $('body, html').animate({scrollTop: ($('.camera-view').offset().top - 15)});
    }

    //listener for when window is small. The fullscreen is disable
    $( window ).resize(function() {
        if (window.matchMedia('(max-width: 400px)').matches) {
          $('.camera-view').removeClass('fullscreen');
          $('.info').removeClass('fullscreen');
        }
    });
    this.render();
  },
  _formatTime: function(seconds)
  {
    if (seconds == null || isNaN(seconds)) {
      return ['--','--','--'];
    }

    var sec_num = parseInt(seconds, 10); // don't forget the second param
    var hours   = Math.floor(sec_num / 3600);
    var minutes = Math.floor((sec_num - (hours * 3600)) / 60);
    var seconds = sec_num - (hours * 3600) - (minutes * 60);

    if (hours   < 10) {hours   = "0"+hours;}
    if (minutes < 10) {minutes = "0"+minutes;}
    if (seconds < 10) {seconds = "0"+seconds;}
    return [hours, minutes, seconds];
  }
});


var PrintingView = Backbone.View.extend({
el: '#printing-view',
  events: {
    'click button.stop-print': 'stopPrint',
    'click button.pause-print': 'togglePausePrint',
    'click button.controls': 'showControlPage',
    'show': 'show',
    'hide': 'onHide'
  },
  semiCircleTemp_views: {},
  extruders_count: null,
  heated_bed: null,
  slidesToShow: null,
  photoView: null,
  printing_progress: null,
  paused: null,
  cancelDialog: null,
  classNoCenter: null,
  currentTool: null,
  initialize: function()
  {
    new SemiCircleProgress();

    var profile = app.printerProfile.toJSON();
    this.currentTool = app.socketData.attributes.tool;
    console.log("Printing initialize", this.currentTool)
    this.extruders_count = profile.extruder_count;

    this.slidesToShow = 3;
    if (this.extruders_count != 1){
      this.classNoCenter = 'no-center';
    }

    this.heated_bed = profile.heated_bed;

    this.renderCircleTemps();

    this.printing_progress = app.socketData.get('printing_progress');
    this.paused = app.socketData.get('paused');

    this.listenTo(app.socketData, 'change:temps', this.onTempsChanged);
    this.listenTo(app.socketData, 'change:paused', this.onPausedChanged);
    this.listenTo(app.socketData, 'change:printing_progress', this.onProgressChanged);
    this.listenTo(app.socketData, 'change:tool', this.onToolChanged);

    this.photoView = new PhotoView({parent: this});
  },
  render: function()
  {
    //Progress data
    var filenameNode = this.$('.progress .filename');

    console.log("render printingview", this.$('progress .filename'))

    if (this.printing_progress) {
      if (filenameNode.text() != this.printing_progress.printFileName) {
        filenameNode.text(this.printing_progress.printFileName);
      }

      //progress bar
      this.$el.find('.progress .meter').css('width', this.printing_progress.percent+'%');
      this.$el.find('.progress .progress-label').text(this.printing_progress.percent+'%');

      //time
      var time = this._formatTime(this.printing_progress.time_left);
      this.$el.find('.estimated-hours').text(time[0]);
      this.$el.find('.estimated-minutes').text(time[1]);
      this.$el.find('.estimated-seconds').text(time[2]);

      //layers
      this.$el.find('.current-layer').text(this.printing_progress.current_layer);
      if (this.printing_progress.layer_count) {
        this.$el.find('.layer-count').text(this.printing_progress.layer_count);
      }

      //heating up
      if (this.printing_progress.heating_up) {
        this.$el.addClass("heating-up");
      } else {
        this.$el.removeClass("heating-up");
      }
    }

    //Paused state
    var pauseBtn = this.$el.find('button.pause-print');
    var controlBtn = this.$el.find('button.controls');

    if (this.paused) {
      pauseBtn.html('<i class="icon-play"></i> Resume Print');
      controlBtn.show();
    } else {
      pauseBtn.html('<i class="icon-pause"></i> Pause Print');
      controlBtn.hide();
    }
  },
  renderCircleTemps: function() {
    var socketTemps = app.socketData.attributes.temps;
    var temps = null;
    var semiCircleTemp = null;

    //extruders
    for (var i = 0; i < this.extruders_count; i++) {
      semiCircleTemp = new TempSemiCircleView({'tool': i, enableOff: false});
      this.semiCircleTemp_views[i] = semiCircleTemp;

      this.$el.find('#slide-extruders').append(this.semiCircleTemp_views[i].render().el);

      if (_.has(socketTemps, 'extruders')) {
        temps = {current: socketTemps.extruders[i].current, target: socketTemps.extruders[i].target};
      } else {
        temps = {current: null, target: null};
      }
      this.semiCircleTemp_views[i].setTemps(temps.current, temps.target);
    }

    //bed
    if (this.heated_bed) {
      this.$el.find('#bed-container').removeClass('no-bed');
    } else {
      this.$el.find('#bed-container').addClass('no-bed');
    }

    semiCircleTemp = new TempSemiCircleView({'tool': null, enableOff: false});
    this.semiCircleTemp_views[this.extruders_count] = semiCircleTemp;
    this.$el.find('.bed').append(this.semiCircleTemp_views[this.extruders_count].render().el);

    if (_.has(socketTemps, 'bed')) {
      temps = {current: socketTemps.bed.actual, target: socketTemps.bed.target};
    } else {
      temps = {current: null, target: null};
    }

    this.semiCircleTemp_views[this.extruders_count].setTemps(temps.current, temps.target);

    for (var i = 0; i <= this.extruders_count; i++) {
      $("#"+this.semiCircleTemp_views[i].el.id+" .progress-temp-circle").circleProgress({
        value: temps.current,
        arcCoef: 0.55,
        size: 180,
        thickness: 20,
        fill: { gradient: ['#60D2E5', '#E8A13A', '#F02E19'] }
      });
    }
  },
  onTempsChanged: function(s, value)
  {
    var temps = {};

    for (var i = 0; i < Object.keys(this.semiCircleTemp_views).length; i++) {
      if (this.semiCircleTemp_views[i].el.id == 'bed' ) {
        temps = {'current': value.bed.actual, 'target': value.bed.target};
      } else {
        temps = {'current': value.extruders[i].current, 'target': value.extruders[i].target};
      }
      (this.semiCircleTemp_views[i]).updateValues(temps);

      if (this.semiCircleTemp_views[i].type == 'tool') {
        var search = '#temp-'+i;
        var tempValue = '--';
        if (this.semiCircleTemp_views[i].actual != null) {
          tempValue = Math.round(this.semiCircleTemp_views[i].actual) + 'º';
        }
        this.$el.find(search).find('.all-temps').text(tempValue);
      }
    }
  },
  onProgressChanged: function(s, value)
  {
    this.printing_progress = value;
    this.render();
  },
  onPausedChanged: function(s, value)
  {
    this.paused = value;
    this.render();
    this.photoView.render();
  },
  onToolChanged: function(s, value)
  {
    console.log("cambia el tool", value)
    //$('#slide-extruders').slick('slickGoTo', value, false);
  },
  _formatTime: function(seconds)
  {
    if (seconds == null || isNaN(seconds)) {
      return ['--','--','--'];
    }

    var sec_num = parseInt(seconds, 10); // don't forget the second param
    var hours   = Math.floor(sec_num / 3600);
    var minutes = Math.floor((sec_num - (hours * 3600)) / 60);
    var seconds = sec_num - (hours * 3600) - (minutes * 60);

    if (hours   < 10) {hours   = "0"+hours;}
    if (minutes < 10) {minutes = "0"+minutes;}
    if (seconds < 10) {seconds = "0"+seconds;}
    return [hours, minutes, seconds];
  },
  showTemps: function()
  {
    var semiCircleCount = Object.keys(this.semiCircleTemp_views).length;
    var socketTemps = app.socketData.attributes.temps;


    for (var i = 0; i < semiCircleCount; i++) {
      if (i != this.extruders_count) {
        if (_.has(socketTemps, 'extruders')) {
          temps = {current: socketTemps.extruders[i].current, target: socketTemps.extruders[i].target};
        } else {
          temps = {current: null, target: null};
        }
      } else {
        if (i == this.extruders_count && this.heated_bed) {
          if (_.has(socketTemps, 'bed')) {
            temps = {current: socketTemps.bed.actual, target: socketTemps.bed.target};
          } else {
            temps = {current: null, target: null};
          }
        }
      }
      this.semiCircleTemp_views[i].updateValues(temps);
    }


    if (this.$('#slide-extruders').hasClass('slick-initialized')) {
      console.log("antes del unslick ShowTemps extruders")
      //this.extrudersSlide.slick('getSlick').unslick();
      this.$('#slide-extruders').slick('unslick');
    }

    this.$('#slide-extruders').slick({
      centerMode: true,
      centerPadding: '10px',
      arrows: true,
      prevArrow: '<i class="icon-angle-left"></i>',
      nextArrow: '<i class="icon-angle-right"></i>',
      slidesToShow: this.slidesToShow,
      slidesToScroll: 1,
      dots: true,
      customPaging : function(slider, i) {
        var tempId = "temp-" + i;
        return '<div id='+ tempId +'><a class="extrusor-number">' + (i+1) + '</a><span class="all-temps"></span></div>';
      },
      focusOnSelect: true,
      infinite: false,
      responsive: [{
        breakpoint: 550,
        settings: {
          slidesToShow: 1,
          slidesToScroll: 1
        }
      }]
    });


    // needed to show the 'dots' (extruders) always
    if (this.extruders_count <= this.slidesToShow){
      this.$('#slide-extruders').slick('slickSetOption', 'slidesToShow', (this.extruders_count-1), true);
      this.$('#slide-extruders').slick('slickSetOption', 'variableWidth', true, true);

      this.$('#slide-extruders').find('.slick-dots a').on('click', function(){
        return true;
      });
    }

    // disable arrows when extruders_count = 1
    if (this.extruders_count == 1) {
      this.$el.find('.slick-slider').find('.slick-arrow').addClass('arrow-disabled');
    }

    this.$('#slide-extruders').find('.slick-track').addClass(this.classNoCenter);

    // On before slide change
    this.$('#slide-extruders').on('beforeChange', _.bind(function(event, slick, currentSlide, nextSlide){
      if (this.extruders_count <= this.slidesToShow) {
        this.$('#slide-extruders').find('.slick-track').addClass(this.classNoCenter);
      } else {
        if (nextSlide > (this.slidesToShow/2)) {
          this.$('#slide-extruders').find('.slick-track').removeClass(this.classNoCenter);
        } else {
          this.$('#slide-extruders').find('.slick-track').addClass(this.classNoCenter);
        }
      }

    }, this));

    // On after slide change
    this.$('#slide-extruders').on('afterChange', _.bind(function(event, slick, currentSlide){
      var currentElement = this.$('#slide-extruders').find('.slick-current').find('.current');
      currentElement.addClass('animated pulse');
      currentElement.one('webkitAnimationEnd mozAnimationEnd MSAnimationEnd oanimationend animationend', function(){
        currentElement.removeClass('pulse');
      }.bind(this));

    }, this));

  },
  show: function()
  {
    this.printing_progress = app.socketData.get('printing_progress');
    this.paused = app.socketData.get('paused');
    this.render();
    this.showTemps();
    this.photoView.render();
  },
  onHide: function()
  {
    this.photoView.onPrintingHide();
  },
  stopPrint: function(e)
  {
    if (!this.cancelDialog) {
      this.cancelDialog = new CancelPrintDialog({parent: this});
    }

    this.cancelDialog.open();
  },
  togglePausePrint: function(e)
  {
    var loadingBtn = $(e.target).closest('.loading-button');
    var wasPaused = app.socketData.get('paused');

    loadingBtn.addClass('loading');
    this._jobCommand('pause', null, function(data){
      if (data && _.has(data, 'error')) {
        console.error(data.error);
      } else {
        app.socketData.set('paused', !wasPaused);
      }
      loadingBtn.removeClass('loading');
    });
  },
  showControlPage: function()
  {
    app.router.navigate('control', {trigger: true, replace: true});
    this.$el.addClass('hide');
  },
  _jobCommand: function(command, data, callback)
  {
    $.ajax({
      url: API_BASEURL + "job",
      type: "POST",
      dataType: "json",
      contentType: "application/json; charset=UTF-8",
      data: JSON.stringify(_.extend({command: command}, data))
    }).
    done(function(data){
      if (callback) callback(data);
    }).
    fail(function(error) {
      if (callback) callback({error:error.responseText});
    });
  }
});

var CancelPrintDialog = Backbone.View.extend({
  el: '#cancel-print-modal',
  printJobId: null,
  events: {
    'click button.yes': 'onYesClicked',
    'click button.send': 'onSendClicked',
    'click button.no': 'close',
    'change input[name=reason]': 'onReasonChanged'
  },
  parent: null,
  initialize: function(params)
  {
    this.parent = params.parent;
  },
  open: function()
  {
    this.printJobId = null;
    this.$el.foundation('reveal', 'open');
    this.$("input[name=reason]").prop("checked", false);
    this.$("input[name=other_text]").val('').addClass('hide');
    this.$('.ask').removeClass('hide');
    this.$('.reasons').addClass('hide').find('h3').removeClass('animated bounceIn');
  },
  close: function()
  {
    this.$el.foundation('reveal', 'close');
  },
  onYesClicked: function(e)
  {
    e.preventDefault();

    var loadingBtn = $(e.target).closest('.loading-button');

    loadingBtn.addClass('loading');

    this.parent._jobCommand('cancel', null, _.bind(function(data) {
      this.parent.photoView.onHide();

      if (data && _.has(data, 'error')) {
        var error = JSON.parse(data.error);
        if (error.id == 'no_active_print') {
          noty({text: "No Print Job is active", type: "warning" , timeout: 3000});
          this.close();
        } else {
          noty({text: "There was an error canceling your job.", timeout: 3000});
        }
        loadingBtn.removeClass('loading');
      } else {
        if (data.print_job_id) {
          this.printJobId = data.print_job_id;
          this.$('.ask').addClass('hide');
          this.$('.reasons').removeClass('hide').find('h3').addClass('animated bounceIn');
          loadingBtn.removeClass('loading');
        } else {
          setTimeout(_.bind(function() {
            loadingBtn.removeClass('loading');
            this.close();
          }, this), 1500);
        }
      }
    }, this));
  },
  onSendClicked: function(e)
  {
    var reasonVal = this.$("input[name=reason]:checked").val();

    if (reasonVal && this.printJobId) {
      var loadingBtn = $(e.target).closest('.loading-button');
      var reasonData = null;

      loadingBtn.addClass('loading');

      reasonData = {
        reason: reasonVal
      };

      if (reasonVal == 'other') {
        var otherText = this.$("input[name=other_text]").val();

        if (otherText) {
          reasonData['other_text'] = otherText;
        }
      }

      $.ajax({
        url: API_BASEURL + 'astroprint/print-jobs/'+this.printJobId+'/add-reason',
        type: "PUT",
        dataType: "json",
        contentType: "application/json; charset=UTF-8",
        data: JSON.stringify(reasonData)
      })
        .always(_.bind(function(){
          loadingBtn.removeClass('loading');
          this.close();
        }, this))
        .fail(function(error) {
          console.error(error);
        });
    } else {
      this.close();
    }
  },
  onReasonChanged: function(e)
  {
    var value = $(e.currentTarget).val();
    var otherText = this.$('input[name=other_text]');

    if (value == 'other') {
      otherText.removeClass('hide').focus();
    } else {
      otherText.addClass('hide');
    }
  }
});
