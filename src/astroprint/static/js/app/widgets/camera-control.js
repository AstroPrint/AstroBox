var CameraControlView = Backbone.View.extend({
	cameraMode: 'video',//['video','photo']
	state: null,
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
	buttonEvent: function(e, text)
	{
		this.$('.loading-button').addClass('loading');
		
		if(this.cameraMode == 'video'){
			if(this.state == 'streaming'){
				this.stopStreaming();
			} else {
				this.startStreaming();
			}
		} else { //photo
			this.takePhoto(text);
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
	takePhoto: function(text) 
	{
		$('.icon-3d-object').hide();

		this.$('.loading-button').addClass('loading');

		setTimeout(_.bind(function(){
			var queryParams = [
				"timestamp=" + (Date.now() / 1000)
			];

			if (text) {
				queryParams.push("text="+encodeURIComponent(text));
			}

			this.$('.camera-image').attr('src', '/camera/snapshot?' + queryParams.join("&"));

			
			this.$('.camera-image').load(_.bind(function() {
				this.$('.loading-button').removeClass('loading');
			},this));

			this.$('.camera-image').error(_.bind(function() {//NOT TESTED YET
				this.$('.loading-button').removeClass('loading');
				this.$('.camera-image').removeAttr('src');
				$('.icon-3d-object').show();
			},this));

		},this),100);
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
					$(document).off("visibilitychange",onVisibilityChange);
					this.browserNotVisibleManager = null;
					this.startStreaming();
				}
			}
		},this);

		$(document).on("visibilitychange", onVisibilityChange);
	},

	//Implement these
	cameraInitialized: function(){},
	startStreaming: function(e){},
	stopStreaming: function(e){}
});

var CameraControlViewMJPEG = CameraControlView.extend({
	managerName: 'mjpeg',
	cameraInitialized: function()
	{
		console.log('cameraInitialized');
	},
	startStreaming: function(e)
	{
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
				this.$('#video-stream').attr('src', '/webcam/?action=stream');
				this.setState('streaming');
				this.activateWindowHideListener();
			}, this));
	},
	stopStreaming: function(e)
	{
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
			}, this));
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
  ableWebRtc: null,//['ready','nowebrtc']
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
			//this.ableWebRtc = false;
			
			this.$('#camera-mode-slider').hide();
			this.ableWebRtc = false;
			
			////////////////////////
		} else {
			this.setState('ready'); 
			this.ableWebRtc = true;
		}
	} else {
		this.setState('nowebrtc');
		this.ableWebRtc = false;
	}

	if( !this.ableWebRtc){
		this.initJanus = null;
		this.startStreaming = function(){ this.setState('nowebrtc'); };
		this.stopStreaming = function(){ return true; };
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
  startStreaming: function(e)
  {	  
	
	this.setState('preparing');
	$.ajax({
			url: API_BASEURL + "camera/init-janus",
			type: "POST",
			dataType: "json",
			contentType: "application/json; charset=UTF-8",
			data: ''
	})
	.done(_.bind(function(isJanusRunning){
		if(!this.$('#remotevideo').is(':visible')) {			
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
						data: JSON.stringify()
					}).done(_.bind(function(response) {
						this.streaming = true;

						var streamingPlugIn = null;
						var selectedStream = this.settings.encoding == 'h264' ? 1 : 2;
						console.log('Starting ' + this.settings.encoding);
						var sizeVideo = this.settings.size;

						//Attach to streaming plugin
						janus.attach({
							plugin: "janus.plugin.streaming",
							success: _.bind(function(pluginHandle) {
								this.streamingPlugIn = pluginHandle;
								console.log('Janus Streaming PlugIn Created');
								
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
										this.setState('ready');
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
									console.log('ERROR');
									this.setState('error');
								},this));

								window.setTimeout(_.bind(function(){
									if(!isPlaying){
										console.log('Timeout!!!');
										console.log('Stop Janus caused by timeout!!!');
										this.stopStreaming();
										this.setState('error');
										this.$('.loading-button').removeClass('loading');
									}
								},this),40000);
								
								var isPlaying = false;
								
								$("#remotevideo").bind("playing",_.bind(function () {
									this.setState('streaming');
									isPlaying = true;
									this.$('.loading-button').removeClass('loading');

									this.activateWindowHideListener();

								},this));
								
								attachMediaStream($('#remotevideo').get(0), stream);

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
				},this),
				destroyed: _.bind(this.initJanus, this)
			});
		}
	},this))	
	.fail(_.bind(function(error){
		noty({text: "Unable to start the WebRTC system.", timeout: 3000});
		this.initJanus();
	}, this));
  },
  stopStreaming: function(e)
  {
	if (this.streaming) { 
		var body = { "request": "stop" };
		this.streamingPlugIn.send({"message": body});
	}	
  }
});
