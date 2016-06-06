var CameraControlView = Backbone.View.extend({
	cameraMode: 'video',//['video','photo']
	state: null,
	canStream: false,
	cameraAvailable: false,
	browserNotVisibleManager: null,
	initCamera: function(settings)
	{
		this.videoStreamingError = null;
		
		$.getJSON(API_BASEURL + 'camera/connected')
		.done(_.bind(function(response){
				
			if(response.isCameraConnected){

				$.getJSON(API_BASEURL + 'camera/has-properties')
				.done(_.bind(function(response){
						if(response.hasCameraProperties){
							this.cameraAvailable = true;
							//video settings
							if( settings ){
								this.settings = settings;
								this.cameraInitialized();

							} else {
								$.getJSON(API_BASEURL + 'settings/camera')
								.done(_.bind(function(settings){
									
									this.settings = settings;
									this.cameraInitialized();

								},this));
							}

							this.render();
						} else {
							this.videoStreamingError = 'Camera error: it is not posible to get the camera capabilities. Please, try to reconnect the camera and try again...';
							this.render();
						}
				},this))
				.fail(_.bind(function(response){
					noty({text: "Unable to communicate with the camera.", timeout: 3000});
					this.stopStreaming();
					this.setState('error');
				},this));
			} else { 
				this.render(); 
			}
		},this))
	},
	buttonEvent: function()
	{		
		if(this.cameraMode == 'video'){
			if(this.state == 'streaming'){
				this.deactivateWindowHideListener();
				return this.stopStreaming();
			} else {
				return this.startStreaming();
			}
		} else { //photo
			return this.takePhoto();
		}
	},
	render: function() 
	{
		this.$el.html(this.template());
	},
	cameraModeChanged: function(e)
	{
		e.preventDefault();

		if(this.cameraMode == 'video'){
			this.stopStreaming();
			this.$el.removeClass('nowebrtc error');
		}
		this.cameraMode = this.cameraModeByValue($(e.currentTarget).is(':checked'));
		this.render();
	},
	cameraModeByValue: function(value)
	{
		/* Values matches by options:
		* - True: video mode
		* - False: photo mode
		*/
		return value ? 'video' : 'photo';
	},
	onShow: function()
	{
		this.initCamera();
		this.$el.removeClass('nowebrtc error');
	},
	onHide: function()
	{
		if(this.cameraMode == 'video'){
			if(this.state == 'streaming'){
				this.stopStreaming();
			}
		} else { 
			this.$('.camera-image').removeAttr('src');
		}
	},
	setState: function(state)
	{
		this.state = state;
		this.$el.removeClass('preparing error nowebrtc streaming ready').addClass(state)  
	},
	takePhoto: function() 
	{
		var promise = $.Deferred();

		photoCont = this.getPhotoContainer();

		photoCont.attr('src', '/camera/snapshot?timestamp=' + (Date.now() / 1000));

		photoCont.on('load',function() {
			photoCont.off('load');
			promise.resolve();
		});

		photoCont.on('error', function() {
			photoCont.removeAttr('src');
			photoCont.off('error');
			promise.reject();
		});

		return promise;
	},
	activateWindowHideListener: function()
	{
		var onVisibilityChange = _.bind(function() {
			if(document.hidden || document.visibilityState != 'visible'){
				this.browserNotVisibleManager = setInterval(_.bind(function(){
					if(document.hidden || document.visibilityState != 'visible'){
						this.stopStreaming();
						clearInterval(this.browserNotVisibleManager);
						this.browserNotVisibleManager = 'waiting';
					}
				},this), 15000);
			} else {
				if(this.browserNotVisibleManager == 'waiting'){
					this.browserNotVisibleManager = null;
					this.startStreaming();
				}
			}
		},this);

		$(document).on("visibilitychange", onVisibilityChange);
	},
	deactivateWindowHideListener: function(){
		$(document).off("visibilitychange");
	},

	//Implement these
	cameraInitialized: function(){},
	startStreaming: function(){}, // return a promise
	stopStreaming: function(){}, // return a promise

	getPhotoContainer: function(){},
	getVideoContainer: function(){}
});

var CameraControlViewMJPEG = CameraControlView.extend({
	managerName: 'mjpeg',
	canStream: true,
	startStreaming: function()
	{
		var promise = $.Deferred();

		this.setState('preparing');

		$.ajax({
			url: API_BASEURL + 'camera/peer-session',
			method: 'POST',
			data: JSON.stringify({
				sessionId: AP_SESSION_ID
			}),
			contentType: 'application/json',
			type: 'json'
		})
			.done(_.bind(function(r){
				this.streaming = true;
				var videoCont = this.getVideoContainer();
				videoCont.attr('src', '/webcam/?action=stream');

				videoCont.on('load', _.bind(function() {
					this.setState('streaming');
					this.activateWindowHideListener();
					videoCont.off('load');
					promise.resolve();
				},this));

				videoCont.on('error', _.bind(function() {
					this.setState('error');
					videoCont.off('error');
					promie.reject()
				},this));
			}, this));

		return promise;
	},
	stopStreaming: function()
	{
		var promise = $.Deferred();

		$.ajax({
			url: API_BASEURL + 'camera/peer-session',
			method: 'DELETE',
			type: 'json',
			contentType: 'application/json',
			data: JSON.stringify({
				sessionId: AP_SESSION_ID
			})
		})
			.done(_.bind(function(){
				this.setState('ready');
				promise.resolve();
			}, this))
			.fail(function(){
				promise.reject();
			});

		return promise;
	}
});

var CameraControlViewWebRTC = CameraControlView.extend({
  el: null,
  serverUrl: null,
  streamingPlugIn: null,
  streaming: false,
  managerName: 'webrtc',
  events: {
	'hide':'onHide'
  },
  settings: null,
  print_capture: null,
  photoSeq: 0,
  _socket: null,
  videoStreamingEvent: null,
  videoStreamingError: null,
  manageVideoStreamingEvent: function(value)
  {//override this for managing this error
	this.videoStreamingError = value.message;
	console.error(value.message);
  },
  _onVideoStreamingError: function(e)
  {
	if (e.data && e.data['event']) {
		var data = e.data['event'];
		var type = data["type"];

		if (type == 'GstreamerFatalErrorManage') {
			this.manageVideoStreaming(data["message"]);
		}
	}
  },
  cameraInitialized: function()
  {
	//Evaluate if we are able to do WebRTC

	if(Janus.isWebrtcSupported()) {
		if(!(navigator.mozGetUserMedia) 
				&&
			!(this.settings.encoding == 'vp8')
		){
			//BROWSER IS NOT FIREFOX
			//AND VIDEO IS NOT VP8
			
			//this.setState('nowebrtc');
			//this.canStream = false;
			
			this.$('#camera-mode-slider').hide();
			this.canStream = false;
			
			////////////////////////
		} else {
			this.setState('ready'); 
			this.canStream = true;
		}
	} else {
		this.setState('nowebrtc');
		this.canStream = false;
	}

	if( !this.canStream){
		this.initJanus = null;
		this.startStreaming = function(){ this.setState('nowebrtc'); return $.Deferred().resolve(); };
		this.stopStreaming = function(){ return $.Deferred().resolve(); };
		this.onHide = function(){ return true; };
		//this.setState('nowebrtc');
		this.cameraMode = 'photo';
	} else {
		this.serverUrl = "http://" + window.location.hostname + ":8088/janus";
		startStreaming = this.startStreaming;
		this.initJanus();

		// Initialize the library (all console debuggers enabled)
		Janus.init({debug: "all", callback: function() {
			console.log('Janus Initialized')
		}});
	}
	this.render();
  },
  initJanus: function()
  {
  	this.streaming = false;
	this.streamingPlugIn = null;
  },
  startStreaming: function()
  {
	var promise = $.Deferred();

	var videoCont = this.getVideoContainer();

	this.setState('preparing');
	$.ajax({
		url: API_BASEURL + "camera/init-janus",
		type: "POST",
		dataType: "json",
		contentType: "application/json; charset=UTF-8",
		data: ''
	})
	.done(_.bind(function(isJanusRunning){
		if(!videoCont.is(':visible')) {			
			// Create session
			var janus = new Janus({
				server: this.serverUrl,
				apisecret: 'd5faa25fe8e3438d826efb1cd3369a50',
				success: _.bind(function() {
					$.ajax({
						url: API_BASEURL + "camera/peer-session",
						type: "POST",
						data: JSON.stringify({
							sessionId: AP_SESSION_ID
						}),
						dataType: "json",
						contentType: "application/json; charset=UTF-8",
					})
					.fail(_.bind(function(){
						noty({text: "Unable to start WebRTC session.", timeout: 3000});
						this.setState('error');
					}, this))
					.done(_.bind(function(response) {
						this.streaming = true;

						var streamingPlugIn = null;
						var selectedStream = this.settings.encoding == 'h264' ? 1 : 2;
						var sizeVideo = this.settings.size;

						//Attach to streaming plugin
						janus.attach({
							plugin: "janus.plugin.streaming",
							success: _.bind(function(pluginHandle) {
								this.streamingPlugIn = pluginHandle;
								
								this.streamingPlugIn.oncleanup = _.bind(function(){
									var body = { "request": "destroy" };
									this.streamingPlugIn.send({"message": body});

									$.ajax({
										url: API_BASEURL + "camera/peer-session",
										type: "DELETE",
										dataType: "json",
										contentType: "application/json; charset=UTF-8",
										data: JSON.stringify({
											sessionId: AP_SESSION_ID
										})
									})
									.done(_.bind(function(){
										//this.setState('ready');
										janus.sessionId = null;
									},this))
									.always(_.bind(this.initJanus, this))
									.fail(_.bind(function(){this.setState('error');},this))
								},this);

								var body = { "request": "watch", id: selectedStream };
								this.streamingPlugIn.send({"message": body});
							},this),
							error: function(error) {
								console.error(error);
								noty({text: "Error communicating with the WebRTC system.", timeout: 3000});
							},
							onmessage: _.bind(function(msg, jsep) {
								//console.log(" ::: Got a message :::");
								//console.log(JSON.stringify(msg));
								var result = msg["result"];
									if(result !== null && result !== undefined) {
										if(result["status"] !== undefined && result["status"] !== null) {
											var status = result["status"];
											if(status === 'stopped')
												this.stopStreaming();
										}
									} else if(msg["error"] !== undefined && msg["error"] !== null) {
										console.error(msg["error"]);
										noty({text: "Unable to communicate with the camera.", timeout: 3000});
										this.stopStreaming();
										return;
									}
									if(jsep !== undefined && jsep !== null) {
										//Answer
										this.streamingPlugIn.createAnswer({
											jsep: jsep,
											media: { audioSend: false, videoSend: false },	// We want recvonly audio/video
											success: _.bind(function(jsep) {
												var body = { "request": "start" };
												this.streamingPlugIn.send({"message": body, "jsep": jsep});
											},this),
											error: _.bind(function(error) {
												console.warn("WebRTC error... " + JSON.stringify(error));
												this.setState('error');
											},this)
										});
									}
							}, this),
							onremotestream: _.bind(function(stream) {
								//Starts GStreamer
								$.ajax({
									url: API_BASEURL + "camera/start-streaming",
									type: "POST"
								}).fail(_.bind(function(){
									this.setState('error');
								},this));

								window.setTimeout(_.bind(function(){
									if(!isPlaying){
										this.stopStreaming();
										this.setState('error');
										promise.reject();
									}
								},this),1000);
								
								var isPlaying = false;

								onPlaying = _.bind(function () {
									this.setState('streaming');
									isPlaying = true;
									this.activateWindowHideListener();
									videoCont.off('playing', onPlaying);
									promise.resolve();
								}, this);
								
								videoCont.on("playing", onPlaying);
								
								attachMediaStream(videoCont.get(0), stream);

							},this),
							oncleanup: function() {
								Janus.log(" ::: Got a cleanup notification :::");
							}
						});
						},this)
					);
				}, this),
				error: _.bind(function(error) {
					if(!this.$el.hasClass('ready') 
						&& !this.videoStreamingError //prevent if internal gstreamer error is showing
						){
							console.error(error);
							noty({text: "Unable to start the WebRTC session.", timeout: 3000});
							//This is a fatal error. The application can't recover. We should probably show an error state in the app.
							streamingState = 'stopped';
							this.setState('error');
						}

					promise.resolve();
				},this),
				destroyed: _.bind(this.initJanus, this)
			});
		}

		promise.resolve(); //We didn't start it but it wasn't visible anyway
	},this))	
	.fail(_.bind(function(error){
		noty({text: "Unable to start the WebRTC system.", timeout: 3000});
		this.initJanus();
		promise.resolve();
	}, this));

	return promise;
  },
  stopStreaming: function()
  {
  	this.setState('ready');
	if (this.streaming) { 
		var body = { "request": "stop" };
		this.streamingPlugIn.send({"message": body});
	}

	return $.Deferred().resolve();
  }
});

var CameraControlViewMac = CameraControlView.extend({
	canStream: true,
	startStreaming: function()
	{
		var promise = $.Deferred();

		this.setState('preparing');

		setTimeout(_.bind(function(){
			this.setState('streaming');
			promise.resolve();
		}, this), 1000);

		return promise;
	},
	stopStreaming: function()
	{
		this.setState('ready');
		return $.Deferred().resolve();
	}
});

var CameraViewBase = {
  mjpeg: CameraControlViewMJPEG,
  gstreamer: CameraControlViewWebRTC,
  mac: CameraControlViewMac
}[CAMERA_MANAGER];
