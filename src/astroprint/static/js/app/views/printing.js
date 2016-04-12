/*
 *  (c) Daniel Arroyo. 3DaGoGo, Inc. (daniel@astroprint.com)
 *
 *  Distributed under the GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
 */

 var TempBarHorizontalView = TempBarView.extend({
    containerDimensions: null,
    scale: null,
    type: null,
    dragging: false,
    lastSent: null,
    events: _.extend(TempBarView.prototype.events, {
        'click': 'onClicked'
    }),
    setHandle: function(value) {
        if (!this.dragging) {
            var position = this._temp2px(value);
            var handle = this.$el.find('.temp-target');

            handle.find('span.label').text(value);
            handle.css({transition: 'left 0.5s'});
            handle.css({left: position + 'px'});
            setTimeout(function() {
                handle.css({transition: ''});
            }, 800);
        }
    },
    onTouchMove: function(e) {
        if (this.dragging) {
            e.preventDefault();
            e.stopPropagation();

            var target = this.$('.temp-target');

            if (e.type == 'mousemove') {
                var pageX = e.originalEvent.pageX;
            } else {
                var pageX = e.originalEvent.changedTouches[0].clientX;
            }

            var newLeft = pageX - this.containerDimensions.left - target.innerWidth()/2.0;
            newLeft = Math.min(Math.max(newLeft, this.containerDimensions.minLeft), this.containerDimensions.maxLeft );

            target.find('span.label').text(this._px2temp(newLeft));
            target.css({left: newLeft+'px'});
        }
    },
    onClicked: function(e) {
        e.preventDefault();

        var target = this.$el.find('.temp-target');

        var newLeft = e.pageX - this.containerDimensions.left - target.innerWidth()/2.0;
        newLeft = Math.min(Math.max(newLeft, this.containerDimensions.minLeft), this.containerDimensions.maxLeft);

        var temp = this._px2temp(newLeft);

        this.setHandle(temp);
        this._sendToolCommand('target', this.type, temp);
    },
    onResize: function() {
        var container = this.$el;
        var handle = container.find('.temp-target');
        var currentLabel = container.find('.temp-current');
        var label = container.find('label');

        var width = container.width();
        var maxLeft = currentLabel.position().left - handle.innerWidth();
        var minLeft = label.innerWidth();

        this.containerDimensions = {
            left: container.offset().left,
            width: width,
            maxLeft: maxLeft,
            minLeft: minLeft,
            px4degree: (maxLeft - minLeft) / (this.scale[1] - this.scale[0])
        };
    },
    renderTemps: function(actual, target) {
        var handle = this.$el.find('.temp-target');
        var handleWidth = handle.innerWidth();

        if (target !== null) {
            if (target != handle.find('span.label').text()) {
                this.setHandle(Math.min(Math.round(target), this.scale[1]));
            }
        }

        if (actual !== null) {
            this.$el.find('.temp-current').html(Math.round(actual)+'&deg;');
            this.$el.find('.temp-curret-line').css({left: ( this._temp2px(actual) + handleWidth/2.0 )+'px'});
        }
    },
    _temp2px: function(temp) {
        var px = temp * this.containerDimensions.px4degree;

        return this.containerDimensions.minLeft + px;
    },
    _px2temp: function(px) {
        return Math.round( ( (px - this.containerDimensions.minLeft) / this.containerDimensions.px4degree ) );
    }
});

var PhotoView = CameraControlView.extend({
    el: "#printing-view .camera-view",
    template: _.template( this.$("#photo-printing-template").html()),
    events: {
        'click button.take-pic': 'manageStreaming',
        'change .timelapse select': 'timelapseFreqChanged'
    },
    parent: null,
    print_capture: null,
    photoSeq: 0,
    initialize: function(options) {

        this.parent = options.parent;

        $.post(API_BASEURL + 'camera/is-camera-available')
        .done(_.bind(function(response){
            
            this.cameraAvailable = response.isCameraAvailable;

            //video settings
            $.getJSON(API_BASEURL + 'settings/camera/streaming')
            .done(_.bind(function(settings){
                
                this.settings = settings;

                if(this.cameraAvailable){

                    this.evalWebRtcAbleing();

                    this.listenTo(app.socketData, 'change:print_capture', this.onPrintCaptureChanged);
                    this.listenTo(app.socketData, 'change:printing_progress', this.onPrintingProgressChanged);
                    this.listenTo(app.socketData, 'change:camera', this.onCameraChanged);

                    this.onCameraChanged(app.socketData, app.socketData.get('camera'));

                    this.print_capture = app.socketData.get('print_capture');
                } else {
                    this.setState('nowebrtc');
                    this.ableWebRtc = false
                }

                this.$el.html(this.template());

                this.render();

            },this));
        },this));

    },
    manageStreaming: function(e){

        if(this.ableWebRtc){
            if(this.state == "streaming"){
                this.stopStreaming();
            } else {
                this.startStreaming();
            }
        } else {
            this.refreshPhoto(e);
        }
    },
    render: function() {

        if(!this.ableWebRtc){

            var imageNode = this.$('.camera-image');

            //image
            var imageUrl = null;

            if (this.print_capture && this.print_capture.last_photo) {
                imageUrl = this.print_capture.last_photo;
            } else if (this.parent.printing_progress && this.parent.printing_progress.rendered_image) {
                imageUrl = this.parent.printing_progress.rendered_image;
            }

            if (imageNode.attr('src') != imageUrl) {
                imageNode.attr('src', imageUrl);
            }

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


        
    },
    onCameraChanged: function(s, value) {
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
    onPrintCaptureChanged: function(s, value) {
        this.print_capture = value;
        this.render();
    },
    onPrintingProgressChanged: function(s, value) {
        if (!this.$('.camera-image').attr('src') && value && value.rendered_image) {
            //This allows the change to propagate
            setTimeout(_.bind(function(){
                this.render();
            },this), 1);
        }
    },
    refreshPhoto: function(e) {
        var loadingBtn = $(e.target).closest('.loading-button');
        var printing_progress = this.parent.printing_progress;

        loadingBtn.addClass('loading');

        var text = Math.floor(printing_progress.percent)+'% - Layer '+(printing_progress.current_layer ? printing_progress.current_layer : '1')+( printing_progress.layer_count ? '/'+printing_progress.layer_count : '');
        var img = this.$('.camera-image');

        img.one('load', function() {
            loadingBtn.removeClass('loading');
        });
        img.one('error', function() {
            loadingBtn.removeClass('loading');
            $(this).attr('src', null);
        });
        img.attr('src',this.takePhoto('?text='+encodeURIComponent(text)+'&seq='+this.photoSeq++));
        //img.attr('src', '/camera/snapshot?text='+encodeURIComponent(text)+'&seq='+this.photoSeq++);
    },
    timelapseFreqChanged: function(e) {
        var newFreq = $(e.target).val();

        if (!this.print_capture || newFreq != this.print_capture.freq) {
            $.ajax({
                url: API_BASEURL + "camera/timelapse",
                type: "POST",
                dataType: "json",
                data: {
                    freq: newFreq
                }
            })
            .fail(function(){
                noty({text: "There was an error adjusting your print capture.", timeout: 3000});
            });
        }
    }
});

var PrintingView = Backbone.View.extend({
	el: '#printing-view',
    events: {
        'click button.stop-print': 'stopPrint',
        'click button.pause-print': 'togglePausePrint',
        'click button.controls': 'showControlPage',
        'show': 'show'
    },
    nozzleBar: null,
    bedBar: null,
    photoView: null,
    printing_progress: null,
    paused: null,
    cancelDialog: null,
    initialize: function() {
        this.nozzleBar = new TempBarHorizontalView({
            scale: [0, app.printerProfile.get('max_nozzle_temp')],
            el: this.$el.find('.temp-bar.nozzle'),
            type: 'tool0'
        });
        this.bedBar = new TempBarHorizontalView({
            scale: [0, app.printerProfile.get('max_bed_temp')],
            el: this.$el.find('.temp-bar.bed'),
            type: 'bed'
        });
        this.photoView = new PhotoView({parent: this});

        this.listenTo(app.socketData, 'change:temps', this.onTempsChanged);
        this.listenTo(app.socketData, 'change:paused', this.onPausedChanged);
        this.listenTo(app.socketData, 'change:printing_progress', this.onProgressChanged);
    },
    render: function()
    {
        //Progress data
        var filenameNode = this.$('.progress .filename');

        if (this.printing_progress) {
            if (filenameNode.text() != this.printing_progress.filename) {
                filenameNode.text(this.printing_progress.filename);
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

        var profile = app.printerProfile.toJSON();

        this.nozzleBar.setMax(profile.max_nozzle_temp);

        if (profile.heated_bed) {
            this.bedBar.setMax(profile.max_bed_temp);
            this.bedBar.$el.removeClass('hide');
        } else {
            this.bedBar.$el.addClass('hide');
        }
    },
    onTempsChanged: function(s, value) {
        if (!this.$el.hasClass('hide')) {
            this.nozzleBar.setTemps(value.extruder.actual, value.extruder.target);
            this.bedBar.setTemps(value.bed.actual, value.bed.target);
        }
    },
    onProgressChanged: function(s, value) {
        this.printing_progress = value;
        this.render();
    },
    onPausedChanged: function(s, value) {
        this.paused = value;
        this.render();
        this.photoView.render();
    },
    _formatTime: function(seconds) {
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
    show: function() {
        this.nozzleBar.onResize();
        this.bedBar.onResize();
        this.printing_progress = app.socketData.get('printing_progress');
        this.paused = app.socketData.get('paused');
        this.render();

        /*this.photoView.print_capture = app.socketData.get('print_capture');
        this.photoView.render();*/
    },
    stopPrint: function(e) {
        if (!this.cancelDialog) {
            this.cancelDialog = new CancelPrintDialog({parent: this});
        }

        this.cancelDialog.open();
    },
    togglePausePrint: function(e) {
        var loadingBtn = $(e.target).closest('.loading-button');
        var wasPaused = app.socketData.get('paused');

        loadingBtn.addClass('loading');
        this._jobCommand('pause', function(data){
            if (data && _.has(data, 'error')) {
                console.error(data.error);
            } else {
                app.socketData.set('paused', !wasPaused);
            }
            loadingBtn.removeClass('loading');
        });
    },
    showControlPage: function() {
        app.router.navigate('control', {trigger: true, replace: true});
        this.$el.addClass('hide');
    },
    _jobCommand: function(command, callback) {
        $.ajax({
            url: API_BASEURL + "job",
            type: "POST",
            dataType: "json",
            contentType: "application/json; charset=UTF-8",
            data: JSON.stringify({command: command})
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
    events: {
        'click button.yes': 'cancelClicked',
        'click button.no': 'close'
    },
    parent: null,
    initialize: function(params) {
        this.parent = params.parent;
    },
    open: function() {
        this.$el.foundation('reveal', 'open');
    },
    close: function() {
        this.$el.foundation('reveal', 'close');
    },
    cancelClicked: function(e) {
        e.preventDefault();

        var loadingBtn = $(e.target).closest('.loading-button');

        loadingBtn.addClass('loading');
        this.parent._jobCommand('cancel', _.bind(function(data){

            if(this.parent.photoView.ableWebRtc){
                if(this.parent.photoView.state == "streaming"){
                    this.parent.photoView.stopStreaming();
                }
            }
            
            if (data && _.has(data, 'error')) {
                noty({text: "There was an error canceling your job.", timeout: 3000});
                loadingBtn.removeClass('loading');
            } else {
                //app.socketData.set({printing: false, paused: false});
                setTimeout(_.bind(function(){
                    loadingBtn.removeClass('loading');
                    this.close();
                }, this), 1000);
            }
        }, this));
    }
});
